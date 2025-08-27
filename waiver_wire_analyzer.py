#!/usr/bin/env python3
"""
Sleeper Fantasy Football Waiver Wire Analyzer

This script analyzes available players on the waiver wire to identify:
- Hidden gems with high value but low ownership
- Trending players gaining momentum
- Insurance picks for your roster
- High upside stashes with breakout potential

Usage: python sleeper_trade_analyzer.py --mode waiver

Configuration is loaded from config.json, which contains all customizable parameters
including thresholds, bonuses, and analysis settings.
"""

import requests
import json
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import time

# Import shared components from the main analyzer
from sleeper_trade_analyzer import (
    ConfigLoader, SleeperAPI, PlayerValueAnalyzer, 
    PerformanceTracker, ExternalADPProvider, config
)

class WaiverWireAnalyzer:
    """Analyze waiver wire players for pickup opportunities"""
    
    def __init__(self, league_id: str = None):
        self.league_id = league_id or config.get_str("league.default_league_id")
        self.api = SleeperAPI()
        self.user_id = None
        self.user_roster = None
        self.all_rostered_players = set()
        self.available_players = {}
        self.value_analyzer = None
        
    def load_league_data(self):
        """Load league data and identify target user"""
        print(f"Loading league data for waiver wire analysis...")
        
        # Get league info
        self.league_info = self.api.get_league_info(self.league_id)
        print(f"League: {self.league_info['name']}")
        
        # Get users and find target user
        users = self.api.get_league_users(self.league_id)
        target_display_name = config.get_str("user.display_name")
        
        for user in users:
            if user.get('display_name') == target_display_name:
                self.user_id = user['user_id']
                print(f"Found target user: {target_display_name} (ID: {self.user_id})")
                break
        
        if not self.user_id:
            raise ValueError(f"Could not find user with display name: {target_display_name}")
        
        # Get rosters and identify user's roster
        rosters = self.api.get_league_rosters(self.league_id)
        
        for roster in rosters:
            if roster.get('owner_id') == self.user_id:
                self.user_roster = roster
                print(f"Found user roster with {len(roster.get('players', []))} players")
            
            # Collect all rostered players across the league
            for player_id in roster.get('players', []):
                self.all_rostered_players.add(player_id)
        
        if not self.user_roster:
            raise ValueError(f"Could not find roster for user: {target_display_name}")
        
        print(f"Total rostered players in league: {len(self.all_rostered_players)}")
        
        # Load players database and set up value analyzer
        players_db = self.api.get_all_players()
        self.value_analyzer = PlayerValueAnalyzer(self.api, players_db, self.league_id)
        self.value_analyzer.load_trending_data()
        
        # Load draft data if available
        draft_id = self.league_info.get('draft_id')
        if draft_id:
            self.value_analyzer.load_draft_data(draft_id)
        
        # Load performance data
        self.value_analyzer.load_performance_data()
        
        # Filter to available players only
        self._filter_available_players(players_db)
    
    def _filter_available_players(self, players_db: Dict):
        """Filter players database to only available (unrostered) players"""
        focus_positions = config.get_list("waiver_wire_analyzer.focus_positions")
        exclude_positions = config.get_list("waiver_wire_analyzer.exclude_positions")
        injury_filters = config.get_list("waiver_wire_analyzer.injury_status_filter")
        min_threshold = config.get_int("waiver_wire_analyzer.minimum_value_threshold")
        
        available_count = 0
        error_count = 0
        
        for player_id, player_info in players_db.items():
            try:
                # Skip if player is rostered
                if player_id in self.all_rostered_players:
                    continue
                
                position = player_info.get('position', 'UNKNOWN')
                
                # Skip excluded positions
                if position in exclude_positions:
                    continue
                
                # Only include focus positions
                if focus_positions and position not in focus_positions:
                    continue
                
                # Filter by injury status if specified
                injury_status = player_info.get('injury_status', '')
                if injury_filters and injury_status:
                    if not any(status.lower() in injury_status.lower() for status in injury_filters):
                        continue
                
                # Calculate value score with error handling
                try:
                    value_score = self.value_analyzer.calculate_player_value_score(player_id)
                except Exception as e:
                    error_count += 1
                    if error_count <= 3:  # Only show first few errors
                        player_name = f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip()
                        print(f"Warning: Error calculating value for {player_name} ({player_id}): {e}")
                    continue
                
                # Skip players below minimum threshold
                if value_score < min_threshold:
                    continue
                
                self.available_players[player_id] = {
                    'info': player_info,
                    'value_score': value_score
                }
                available_count += 1
                
            except Exception as e:
                error_count += 1
                if error_count <= 3:  # Only show first few errors
                    print(f"Warning: Error processing player {player_id}: {e}")
                continue
        
        if error_count > 0:
            print(f"Encountered {error_count} errors while processing players")
        print(f"Found {available_count} available players meeting criteria")
    
    def analyze_user_roster_needs(self) -> Dict:
        """Analyze user's roster to identify positional needs"""
        if not self.user_roster:
            return {}
        
        # Count players by position
        position_counts = defaultdict(int)
        user_players = self.user_roster.get('players', [])
        
        for player_id in user_players:
            if player_id in self.value_analyzer.players_db:
                position = self.value_analyzer.players_db[player_id].get('position', 'UNKNOWN')
                position_counts[position] += 1
        
        # Compare to expected counts
        expected_counts = config.get_dict("roster_analyzer.expected_counts")
        needs = []
        strengths = []
        
        for pos, expected in expected_counts.items():
            actual = position_counts.get(pos, 0)
            if actual < expected:
                needs.append(pos)
            elif actual > expected + 1:
                strengths.append(pos)
        
        return {
            'needs': needs,
            'strengths': strengths,
            'position_counts': dict(position_counts)
        }
    
    def categorize_hidden_gems(self) -> List[Dict]:
        """Find hidden gem players - high value but low trending"""
        gems_config = config.get_dict("waiver_wire_analyzer.hidden_gems")
        min_value = gems_config.get("min_value_score", 40)
        max_trending = gems_config.get("max_trending_adds", 50)
        depth_prefs = gems_config.get("depth_chart_preference", [1, 2])
        
        hidden_gems = []
        
        for player_id, data in self.available_players.items():
            value_score = data['value_score']
            player_info = data['info']
            
            # Must meet minimum value threshold
            if value_score < min_value:
                continue
            
            # Check trending data (low trending = hidden)
            trending_score = self.value_analyzer.trending_cache.get(player_id, 0)
            if trending_score > max_trending:
                continue
            
            # Prefer players higher on depth chart
            depth_pos = player_info.get('depth_chart_position', 99)
            if depth_pos not in depth_prefs and depth_pos != 99:
                continue
            
            hidden_gems.append({
                'player_id': player_id,
                'name': f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip(),
                'position': player_info.get('position', 'UNKNOWN'),
                'team': player_info.get('team', ''),
                'value_score': value_score,
                'trending_score': trending_score,
                'depth_chart_pos': depth_pos,
                'category': 'Hidden Gem'
            })
        
        # Sort by value score descending
        hidden_gems.sort(key=lambda x: x['value_score'], reverse=True)
        
        max_results = config.get_int("waiver_wire_analyzer.max_results_per_category", 10)
        return hidden_gems[:max_results]
    
    def categorize_trending_players(self) -> List[Dict]:
        """Find trending players gaining momentum"""
        trending_config = config.get_dict("waiver_wire_analyzer.trending")
        min_adds = trending_config.get("min_add_count", 20)
        
        trending_players = []
        
        for player_id, data in self.available_players.items():
            player_info = data['info']
            
            # Check trending data
            trending_score = self.value_analyzer.trending_cache.get(player_id, 0)
            if trending_score < min_adds:
                continue
            
            trending_players.append({
                'player_id': player_id,
                'name': f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip(),
                'position': player_info.get('position', 'UNKNOWN'),
                'team': player_info.get('team', ''),
                'value_score': data['value_score'],
                'trending_score': trending_score,
                'category': 'Trending Up'
            })
        
        # Sort by trending score descending
        trending_players.sort(key=lambda x: x['trending_score'], reverse=True)
        
        max_results = config.get_int("waiver_wire_analyzer.max_results_per_category", 10)
        return trending_players[:max_results]
    
    def categorize_insurance_picks(self) -> List[Dict]:
        """Find insurance/handcuff players for user's roster"""
        insurance_config = config.get_dict("waiver_wire_analyzer.insurance")
        user_players = self.user_roster.get('players', [])
        
        insurance_picks = []
        
        # Get user's players by team and position for handcuff analysis
        user_teams_positions = defaultdict(list)
        for player_id in user_players:
            if player_id in self.value_analyzer.players_db:
                player_info = self.value_analyzer.players_db[player_id]
                team = player_info.get('team', '')
                position = player_info.get('position', '')
                if team and position:
                    user_teams_positions[team].append({
                        'id': player_id,
                        'position': position,
                        'name': f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip()
                    })
        
        for player_id, data in self.available_players.items():
            player_info = data['info']
            team = player_info.get('team', '')
            position = player_info.get('position', '')
            
            # Check if this player is on same team as user's players
            if team in user_teams_positions:
                for user_player in user_teams_positions[team]:
                    # Same position handcuff (especially RB)
                    if position == user_player['position']:
                        bonus = 0
                        if position == 'RB':
                            bonus = insurance_config.get("rb1_injury_rb2_boost", 35)
                        elif position == 'WR':
                            bonus = insurance_config.get("wr1_injury_wr2_boost", 25)
                        elif position == 'TE':
                            bonus = insurance_config.get("te1_injury_te2_boost", 30)
                        else:
                            bonus = insurance_config.get("handcuff_bonus", 15)
                        
                        if bonus > 0:
                            insurance_picks.append({
                                'player_id': player_id,
                                'name': f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip(),
                                'position': position,
                                'team': team,
                                'value_score': data['value_score'] + bonus,
                                'handcuff_for': user_player['name'],
                                'bonus': bonus,
                                'category': 'Insurance/Handcuff'
                            })
        
        # Sort by adjusted value score
        insurance_picks.sort(key=lambda x: x['value_score'], reverse=True)
        
        max_results = config.get_int("waiver_wire_analyzer.max_results_per_category", 10)
        return insurance_picks[:max_results]
    
    def categorize_high_upside_players(self) -> List[Dict]:
        """Find high upside players with breakout potential"""
        upside_config = config.get_dict("waiver_wire_analyzer.high_upside")
        max_age = upside_config.get("max_age", 28)
        min_exp = upside_config.get("min_years_exp", 0)
        max_exp = upside_config.get("max_years_exp", 5)
        breakout_range = upside_config.get("breakout_age_range", [22, 26])
        
        high_upside = []
        error_count = 0
        
        for player_id, data in self.available_players.items():
            try:
                player_info = data['info']
                
                # Handle None values with safe defaults and type conversion
                age = player_info.get('age')
                if age is None or not isinstance(age, (int, float)):
                    try:
                        age = int(age) if age is not None else 99
                    except (ValueError, TypeError):
                        age = 99
                
                years_exp = player_info.get('years_exp')
                if years_exp is None or not isinstance(years_exp, (int, float)):
                    try:
                        years_exp = int(years_exp) if years_exp is not None else 99
                    except (ValueError, TypeError):
                        years_exp = 99
                
                # Age and experience filters
                if age > max_age or years_exp < min_exp or years_exp > max_exp:
                    continue
                
                # Calculate upside bonus
                upside_bonus = 0
                
                # Rookie bonus
                if years_exp == 0:
                    upside_bonus += upside_config.get("rookie_opportunity", 10)
                
                # Breakout age range bonus (handle None age)
                if age is not None and age != 99 and isinstance(age, (int, float)):
                    try:
                        if breakout_range[0] <= age <= breakout_range[1]:
                            upside_bonus += 15
                    except (TypeError, ValueError):
                        pass  # Skip bonus if comparison fails
                
                # Depth chart promotion potential
                depth_pos = player_info.get('depth_chart_position', 99)
                if depth_pos is not None:
                    try:
                        if isinstance(depth_pos, (int, float)) and depth_pos <= 3:
                            upside_bonus += upside_config.get("depth_chart_promotion", 25)
                    except (TypeError, ValueError):
                        pass  # Skip bonus if comparison fails
                
                high_upside.append({
                    'player_id': player_id,
                    'name': f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip(),
                    'position': player_info.get('position', 'UNKNOWN'),
                    'team': player_info.get('team', ''),
                    'age': age,
                    'years_exp': years_exp,
                    'value_score': data['value_score'] + upside_bonus,
                    'upside_bonus': upside_bonus,
                    'category': 'High Upside'
                })
                
            except Exception as e:
                error_count += 1
                if error_count <= 3:  # Only show first few errors
                    player_name = f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip()
                    print(f"Warning: Error processing high upside player {player_name}: {e}")
                continue
        
        if error_count > 0:
            print(f"Encountered {error_count} errors in high upside analysis")
        
        # Sort by adjusted value score
        high_upside.sort(key=lambda x: x['value_score'], reverse=True)
        
        max_results = config.get_int("waiver_wire_analyzer.max_results_per_category", 10)
        return high_upside[:max_results]
    
    def analyze_waiver_wire(self):
        """Perform complete waiver wire analysis"""
        if not self.available_players:
            self.load_league_data()
        
        print("\n" + "="*70)
        print(f"🔍 WAIVER WIRE ANALYSIS: {self.league_info['name']}")
        print("="*70)
        
        # Analyze user's roster needs
        roster_analysis = self.analyze_user_roster_needs()
        target_user = config.get_str("user.display_name")
        
        print(f"\n📊 {target_user}'s Roster Analysis:")
        print(f"Position Counts: {roster_analysis['position_counts']}")
        if roster_analysis['needs']:
            print(f"🎯 Needs: {', '.join(roster_analysis['needs'])}")
        if roster_analysis['strengths']:
            print(f"💪 Strengths: {', '.join(roster_analysis['strengths'])}")
        
        # Get analysis types from config
        analysis_types = config.get_list("waiver_wire_analyzer.analysis_types")
        
        # Run each analysis type
        if "hidden_gems" in analysis_types:
            hidden_gems = self.categorize_hidden_gems()
            if hidden_gems:
                print(f"\n💎 HIDDEN GEMS ({len(hidden_gems)} found)")
                print("-" * 50)
                self._display_player_recommendations(hidden_gems)
        
        if "trending" in analysis_types:
            trending = self.categorize_trending_players()
            if trending:
                print(f"\n📈 TRENDING PLAYERS ({len(trending)} found)")
                print("-" * 50)
                self._display_player_recommendations(trending)
        
        if "insurance" in analysis_types:
            insurance = self.categorize_insurance_picks()
            if insurance:
                print(f"\n🛡️  INSURANCE PICKS ({len(insurance)} found)")
                print("-" * 50)
                self._display_player_recommendations(insurance, show_handcuff=True)
        
        if "high_upside" in analysis_types:
            high_upside = self.categorize_high_upside_players()
            if high_upside:
                print(f"\n🚀 HIGH UPSIDE STASHES ({len(high_upside)} found)")
                print("-" * 50)
                self._display_player_recommendations(high_upside, show_age=True)
        
        print("\n" + "="*70)
        print("✅ Waiver wire analysis complete!")
        print("💡 Focus on players that match your roster needs and league trends.")
        print("="*70)
    
    def _display_player_recommendations(self, players: List[Dict], show_handcuff: bool = False, show_age: bool = False):
        """Display formatted table of player recommendations"""
        if not players:
            print("No players found matching criteria.")
            return
        
        # Table header
        header = "┌─────────┬──────────────────────┬──────┬───────"
        row_format = "│ {:<7} │ {:<20} │ {:<4} │ {:<5}"
        
        if show_handcuff:
            header += "┬──────────────────────┐"
            row_format += " │ {:<20} │"
            print(header)
            print("│ Pos     │ Player               │ Team │ Value │ Handcuff For         │")
        elif show_age:
            header += "┬─────┬─────┐"
            row_format += " │ {:<3} │ {:<3} │"
            print(header)
            print("│ Pos     │ Player               │ Team │ Value │ Age │ Exp │")
        else:
            header += "┬─────────┐"
            row_format += " │ {:<7} │"
            print(header)
            print("│ Pos     │ Player               │ Team │ Value │ Trend   │")
        
        print("├─────────┼──────────────────────┼──────┼───────" + ("┼──────────────────────┤" if show_handcuff else ("┼─────┼─────┤" if show_age else "┼─────────┤")))
        
        # Table rows
        max_name_length = config.get_int("display.table_max_name_length", 20)
        
        for player in players:
            pos = player['position']
            name = player['name']
            team = player.get('team', '')[:4]  # Limit team to 4 chars
            value = f"{player['value_score']:.1f}"
            
            # Truncate name if too long
            if len(name) > max_name_length:
                name = name[:max_name_length-3] + "..."
            
            if show_handcuff:
                handcuff_for = player.get('handcuff_for', '')[:20]
                print(row_format.format(pos, name, team, value, handcuff_for))
            elif show_age:
                age = str(player.get('age', '?'))
                exp = str(player.get('years_exp', '?'))
                print(row_format.format(pos, name, team, value, age, exp))
            else:
                trend = f"+{player.get('trending_score', 0)}" if player.get('trending_score', 0) > 0 else str(player.get('trending_score', 0))
                print(row_format.format(pos, name, team, value, trend))
        
        # Table footer
        print("└─────────┴──────────────────────┴──────┴───────" + ("┴──────────────────────┘" if show_handcuff else ("┴─────┴─────┘" if show_age else "┴─────────┘")))

def main():
    """Main execution function for waiver wire analysis"""
    league_id = config.get_str("league.default_league_id")
    
    try:
        analyzer = WaiverWireAnalyzer(league_id)
        analyzer.analyze_waiver_wire()
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data from Sleeper API: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
