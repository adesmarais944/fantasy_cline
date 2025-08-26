#!/usr/bin/env python3
"""
Sleeper Fantasy Football Trade Analyzer
Core League Roster Analyzer

This script analyzes your Sleeper fantasy football league to identify:
- Team roster compositions and strengths/weaknesses
- Positional needs and surpluses
- Potential trade opportunities

Usage: python sleeper_trade_analyzer.py
"""

import requests
import json
from typing import Dict, List, Optional
from collections import defaultdict
import time
import statistics

class SleeperAPI:
    """Handle all Sleeper API interactions"""
    
    BASE_URL = "https://api.sleeper.app/v1"
    
    def __init__(self):
        self.session = requests.Session()
        self.players_cache = None
    
    def get_league_info(self, league_id: str) -> Dict:
        """Get league information and settings"""
        url = f"{self.BASE_URL}/league/{league_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_league_rosters(self, league_id: str) -> List[Dict]:
        """Get all rosters in the league"""
        url = f"{self.BASE_URL}/league/{league_id}/rosters"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_league_users(self, league_id: str) -> List[Dict]:
        """Get all users in the league"""
        url = f"{self.BASE_URL}/league/{league_id}/users"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_all_players(self) -> Dict:
        """Get all NFL players (cached for performance)"""
        if self.players_cache is None:
            print("Fetching NFL player database... (this may take a moment)")
            url = f"{self.BASE_URL}/players/nfl"
            response = self.session.get(url)
            response.raise_for_status()
            self.players_cache = response.json()
            print(f"Loaded {len(self.players_cache)} players")
        return self.players_cache
    
    def get_trending_players(self, trend_type: str = "add", hours: int = 24, limit: int = 50) -> List[Dict]:
        """Get trending players (add/drop activity)"""
        url = f"{self.BASE_URL}/players/nfl/trending/{trend_type}"
        params = {"lookback_hours": hours, "limit": limit}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_league_matchups(self, league_id: str, week: int) -> List[Dict]:
        """Get matchup data for a specific week"""
        url = f"{self.BASE_URL}/league/{league_id}/matchups/{week}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_draft_picks(self, draft_id: str) -> List[Dict]:
        """Get all picks in a draft"""
        url = f"{self.BASE_URL}/draft/{draft_id}/picks"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_player_stats(self, player_id: str, season: str = "2024") -> Dict:
        """Get player stats for a season"""
        url = f"{self.BASE_URL}/stats/nfl/player/{player_id}"
        params = {"season": season, "season_type": "regular"}
        response = self.session.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return {}
    
    def get_league_scoring_settings(self, league_id: str) -> Dict:
        """Get league scoring settings"""
        league_info = self.get_league_info(league_id)
        return league_info.get('scoring_settings', {})

class ExternalADPProvider:
    """Fetch external ADP data from fantasy football platforms"""
    
    def __init__(self):
        self.session = requests.Session()
        self.adp_cache = {}
        
    def load_external_adp_data(self) -> Dict:
        """Load external ADP data - using mock data for now"""
        # In a real implementation, this would fetch from FantasyPros, ESPN, etc.
        # For now, using mock data based on typical 2024 ADP ranges
        mock_adp_data = {
            # Top tier players (picks 1-24)
            'christian_mccaffrey': 1, 'austin_ekeler': 65, 'saquon_barkley': 4,
            'jamarr_chase': 2, 'ceedee_lamb': 6, 'puka_nacua': 12,
            'josh_allen': 22, 'lamar_jackson': 28, 'jalen_hurts': 34,
            'travis_kelce': 18, 'mark_andrews': 45, 'george_kittle': 35,
            # Mid-tier players (picks 25-100)
            'davante_adams': 42, 'garrett_wilson': 38, 'mike_evans': 55,
            'derrick_henry': 48, 'jonathan_taylor': 20, 'breece_hall': 30,
            'tyreek_hill': 25, 'amon_ra_st_brown': 32, 'drake_london': 68,
            # Late round values
            'hunter_henry': 145, 'chase_mclaughlin': 180, 'detroit_lions': 165
        }
        
        # Convert to player_id format if needed
        self.adp_cache = mock_adp_data
        print(f"Loaded external ADP data for {len(self.adp_cache)} players")
        return self.adp_cache
    
    def get_external_adp(self, player_name: str) -> Optional[int]:
        """Get external ADP for a player by name"""
        # Normalize player name for lookup
        normalized_name = player_name.lower().replace(' ', '_').replace('.', '').replace("'", '')
        return self.adp_cache.get(normalized_name)

class PerformanceTracker:
    """Track and analyze player performance vs expectations"""
    
    def __init__(self, api: SleeperAPI, league_id: str):
        self.api = api
        self.league_id = league_id
        self.scoring_settings = {}
        self.matchup_data = {}
        self.player_scores = defaultdict(list)
        self.positional_rankings = {}
        
        # Position weights for performance modifiers
        self.position_weights = {
            'QB': 0.2,
            'RB': 0.3,
            'WR': 0.25,
            'TE': 0.15,
            'DEF': 0.05,
            'K': 0.05
        }
    
    def load_performance_data(self):
        """Load fantasy scoring data from league matchups"""
        try:
            print("Loading performance data...")
            self.scoring_settings = self.api.get_league_scoring_settings(self.league_id)
            
            # Load matchup data for available weeks (assuming weeks 1-15)
            current_week = 15  # Adjust based on current NFL week
            
            for week in range(1, min(current_week + 1, 16)):
                try:
                    matchups = self.api.get_league_matchups(self.league_id, week)
                    self.matchup_data[week] = matchups
                    
                    # Extract player scores from matchups
                    for matchup in matchups:
                        if 'players_points' in matchup:
                            for player_id, points in matchup['players_points'].items():
                                self.player_scores[player_id].append({
                                    'week': week,
                                    'points': points
                                })
                except Exception as e:
                    print(f"Warning: Could not load week {week} data: {e}")
                    continue
            
            print(f"Loaded performance data for {len(self.player_scores)} players")
            self._calculate_positional_rankings()
            
        except Exception as e:
            print(f"Warning: Could not load performance data: {e}")
    
    def _calculate_positional_rankings(self):
        """Calculate current positional rankings based on fantasy points"""
        # Group players by position and calculate total points
        position_totals = defaultdict(list)
        
        for player_id, scores in self.player_scores.items():
            # Get player position from the main players database
            # This would need to be passed in or accessed differently
            total_points = sum(score['points'] for score in scores)
            if total_points > 0:  # Only include players with points
                # For now, we'll estimate position based on typical scoring patterns
                # In a full implementation, this would use the actual player position
                position_totals['ALL'].append((player_id, total_points))
        
        # Sort and rank players
        for position, players in position_totals.items():
            players.sort(key=lambda x: x[1], reverse=True)
            self.positional_rankings[position] = {
                player_id: rank + 1 for rank, (player_id, _) in enumerate(players)
            }
    
    def get_player_performance_rank(self, player_id: str, position: str) -> Optional[int]:
        """Get current fantasy ranking for a player at their position"""
        return self.positional_rankings.get(position, {}).get(player_id)
    
    def calculate_expected_rank_from_adp(self, adp: int, position: str) -> int:
        """Convert ADP to expected positional rank"""
        # Rough conversion based on typical draft patterns
        position_multipliers = {
            'QB': 0.08,  # ~12 QBs in first 150 picks
            'RB': 0.25,  # ~37 RBs in first 150 picks  
            'WR': 0.35,  # ~52 WRs in first 150 picks
            'TE': 0.08,  # ~12 TEs in first 150 picks
            'DEF': 0.08, # ~12 DEFs in first 150 picks
            'K': 0.08    # ~12 Ks in first 150 picks
        }
        
        multiplier = position_multipliers.get(position, 0.15)
        expected_rank = max(1, int(adp * multiplier))
        return expected_rank
    
    def calculate_performance_modifier(self, player_id: str, position: str, 
                                     league_adp: Optional[int], external_adp: Optional[int]) -> Dict:
        """Calculate performance modifier based on ADP vs actual performance"""
        
        # Get current performance rank
        current_rank = self.get_player_performance_rank(player_id, position)
        
        if not current_rank:
            return {
                'modifier': 0,
                'reason': 'No performance data',
                'current_rank': None,
                'expected_rank_league': None,
                'expected_rank_external': None
            }
        
        # Calculate expected ranks from both ADPs
        expected_rank_league = None
        expected_rank_external = None
        
        if league_adp and league_adp < 999:
            expected_rank_league = self.calculate_expected_rank_from_adp(league_adp, position)
        
        if external_adp:
            expected_rank_external = self.calculate_expected_rank_from_adp(external_adp, position)
        
        # Use the more conservative (higher) expected rank for modifier calculation
        expected_rank = None
        if expected_rank_league and expected_rank_external:
            expected_rank = max(expected_rank_league, expected_rank_external)
        elif expected_rank_league:
            expected_rank = expected_rank_league
        elif expected_rank_external:
            expected_rank = expected_rank_external
        
        if not expected_rank:
            return {
                'modifier': 0,
                'reason': 'No ADP data',
                'current_rank': current_rank,
                'expected_rank_league': expected_rank_league,
                'expected_rank_external': expected_rank_external
            }
        
        # Calculate rank differential (positive = outperforming)
        rank_differential = expected_rank - current_rank
        
        # Apply position weight and scale to modifier range (-15 to +15)
        position_weight = self.position_weights.get(position, 0.15)
        raw_modifier = rank_differential * position_weight * 2  # Scale factor
        
        # Cap the modifier at ±15 points (halved from original ±30)
        modifier = max(-15, min(15, raw_modifier))
        
        return {
            'modifier': modifier,
            'reason': f"Rank {current_rank} vs {expected_rank} expected",
            'current_rank': current_rank,
            'expected_rank_league': expected_rank_league,
            'expected_rank_external': expected_rank_external,
            'rank_differential': rank_differential
        }

class PlayerValueAnalyzer:
    """Analyze player values using available Sleeper data"""
    
    def __init__(self, api: SleeperAPI, players_db: Dict, league_id: str = None):
        self.api = api
        self.players_db = players_db
        self.trending_cache = {}
        self.draft_data = {}
        self.league_id = league_id
        
        # Initialize performance tracking components
        self.performance_tracker = None
        self.adp_provider = None
        
        if league_id:
            self.performance_tracker = PerformanceTracker(api, league_id)
            self.adp_provider = ExternalADPProvider()
        
    def get_player_value_metrics(self, player_id: str) -> Dict:
        """Get value metrics for a player"""
        player_info = self.players_db.get(player_id, {})
        
        metrics = {
            'search_rank': player_info.get('search_rank', 9999),  # Lower is better
            'depth_chart_position': player_info.get('depth_chart_position', 99),
            'depth_chart_order': player_info.get('depth_chart_order', 99),
            'years_exp': player_info.get('years_exp', 0),
            'age': player_info.get('age', 99),
            'injury_status': player_info.get('injury_status', ''),
            'status': player_info.get('status', 'Unknown'),
            'trending_score': 0  # Will be populated from trending data
        }
        
        return metrics
    
    def load_trending_data(self):
        """Load and cache trending player data"""
        try:
            trending_adds = self.api.get_trending_players("add", 168, 100)  # 7 days, top 100
            trending_drops = self.api.get_trending_players("drop", 168, 100)
            
            # Create trending score: adds are positive, drops are negative
            for player in trending_adds:
                self.trending_cache[player['player_id']] = player['count']
            
            for player in trending_drops:
                current_score = self.trending_cache.get(player['player_id'], 0)
                self.trending_cache[player['player_id']] = current_score - player['count']
                
            print(f"Loaded trending data for {len(self.trending_cache)} players")
        except Exception as e:
            print(f"Warning: Could not load trending data: {e}")
    
    def load_draft_data(self, draft_id: str):
        """Load and cache draft pick data"""
        try:
            draft_picks = self.api.get_draft_picks(draft_id)
            
            # Create draft position lookup: player_id -> draft info
            for pick in draft_picks:
                player_id = pick.get('player_id')
                if player_id:
                    self.draft_data[player_id] = {
                        'pick_no': pick.get('pick_no', 999),
                        'round': pick.get('round', 99),
                        'draft_slot': pick.get('draft_slot', 99)
                    }
            
            print(f"Loaded draft data for {len(self.draft_data)} players")
        except Exception as e:
            print(f"Warning: Could not load draft data: {e}")
    
    def load_performance_data(self):
        """Load performance tracking data"""
        if self.performance_tracker:
            self.performance_tracker.load_performance_data()
        if self.adp_provider:
            self.adp_provider.load_external_adp_data()
    
    def get_draft_tier(self, draft_info: Optional[Dict]) -> int:
        """Determine draft tier based on round"""
        if not draft_info:
            return 3  # Undrafted players are Tier 3
        
        round_num = draft_info.get('round', 99)
        if round_num <= 3:
            return 1  # Tier 1: Elite/Proven Talent (Rounds 1-3)
        elif round_num <= 6:
            return 2  # Tier 2: Solid Contributors (Rounds 4-6)
        else:
            return 3  # Tier 3: Flyers and Depth (Rounds 7+)
    
    def calculate_player_value_score(self, player_id: str) -> float:
        """Calculate a composite value score for a player with enhanced tier-based adjustments"""
        metrics = self.get_player_value_metrics(player_id)
        player_info = self.players_db.get(player_id, {})
        draft_info = self.draft_data.get(player_id)
        position = player_info.get('position', 'UNKNOWN')
        
        # Determine draft tier
        tier = self.get_draft_tier(draft_info)
        
        # Enhanced base score from search rank - increased range for more granularity
        search_rank = metrics['search_rank']
        if search_rank == 9999:  # No rank available
            base_score = 0
        else:
            # Increased to 0-80 scale for more differentiation
            base_score = max(0, 1000 - search_rank) / 12.5  # Scale to 0-80
        
        # Apply tier-based base score multipliers
        tier_multipliers = {1: 1.3, 2: 1.0, 3: 0.7}  # Increased Tier 1 bonus
        base_score *= tier_multipliers[tier]
        
        # Enhanced depth chart bonus with tier scaling
        depth_bonus = 0
        depth_pos = metrics['depth_chart_position']
        if isinstance(depth_pos, (int, float)) and depth_pos != 99:
            tier_depth_multipliers = {1: 1.5, 2: 1.2, 3: 1.0}
            multiplier = tier_depth_multipliers[tier]
            
            if depth_pos == 1:
                depth_bonus = 20 * multiplier
            elif depth_pos == 2:
                depth_bonus = 10 * multiplier
            elif depth_pos <= 3:
                depth_bonus = 5 * multiplier
        
        # Enhanced trending bonus/penalty with tier scaling
        trending_score = self.trending_cache.get(player_id, 0)
        tier_trending_multipliers = {1: 1.3, 2: 1.1, 3: 0.9}
        trending_multiplier = tier_trending_multipliers[tier]
        trending_bonus = min(20, max(-20, trending_score / 5)) * trending_multiplier
        
        # Injury penalty (unchanged)
        injury_penalty = 0
        injury_status = metrics['injury_status']
        if injury_status and isinstance(injury_status, str):
            injury_status_lower = injury_status.lower()
            if 'out' in injury_status_lower or 'ir' in injury_status_lower:
                injury_penalty = -30
            elif 'doubtful' in injury_status_lower:
                injury_penalty = -15
            elif 'questionable' in injury_status_lower:
                injury_penalty = -5
        
        # Enhanced tier-based draft bonus/penalty with more granularity
        draft_bonus = 0
        if draft_info:
            pick_no = draft_info['pick_no']
            round_num = draft_info['round']
            
            if tier == 1:  # Rounds 1-3: Elite talent - more generous bonuses
                if base_score >= 60:  # High performers
                    draft_bonus = 12
                elif base_score >= 45:  # Good performers
                    draft_bonus = 6
                elif base_score < 30:  # Underperforming
                    draft_bonus = -5  # Less harsh penalty
            elif tier == 2:  # Rounds 4-6: Solid contributors
                if base_score >= 50:
                    draft_bonus = 8
                elif base_score < 25:
                    draft_bonus = -5
            else:  # Tier 3: Rounds 7+: Reduced bonus caps
                if base_score >= 40:
                    draft_bonus = 8
                elif base_score < 20:
                    draft_bonus = -3
        
        # Enhanced performance modifier with tier scaling
        performance_modifier = 0
        if self.performance_tracker and self.adp_provider:
            player_name = f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip()
            
            # Get league ADP from draft data
            league_adp = draft_info.get('pick_no') if draft_info else None
            
            # Get external ADP
            external_adp = self.adp_provider.get_external_adp(player_name) if player_name else None
            
            # Calculate performance modifier
            perf_data = self.performance_tracker.calculate_performance_modifier(
                player_id, position, league_adp, external_adp
            )
            raw_performance_modifier = perf_data['modifier']
            
            # Apply tier-based caps with enhanced scaling
            if tier == 1:  # Tier 1: Enhanced range for more differentiation
                performance_modifier = max(-12, min(18, raw_performance_modifier))  # Slightly asymmetric
            elif tier == 2:  # Tier 2: Moderate caps
                performance_modifier = max(-10, min(12, raw_performance_modifier))
            else:  # Tier 3: Restricted caps (maintains our protection)
                performance_modifier = max(-8, min(10, raw_performance_modifier))
        
        # Position-based scarcity adjustments
        position_bonus = 0
        if tier == 1:  # Only apply to elite players
            position_bonuses = {
                'RB': 4,   # RB scarcity premium
                'QB': 2,   # QB positional value
                'TE': 3,   # TE scarcity premium
                'WR': 0,   # Baseline
                'K': -2,   # Less valuable
                'DEF': -2  # Less valuable
            }
            position_bonus = position_bonuses.get(position, 0)
        
        # Calculate total score
        total_score = (base_score + depth_bonus + trending_bonus + injury_penalty + 
                      draft_bonus + performance_modifier + position_bonus)
        
        # Apply flexible tier-based floors and caps
        if tier == 1:  # Elite talent: Floor 85, no cap (allow up to 120+)
            total_score = max(total_score, 85)
        elif tier == 2:  # Solid contributors: Floor 65, soft cap at 95
            total_score = max(total_score, 65)
            if total_score > 95:
                total_score = 95 + (total_score - 95) * 0.3  # Diminishing returns above 95
        else:  # Tier 3: No floor, hard cap at 85 to prevent late-round inflation
            total_score = min(total_score, 85)
        
        return max(0, total_score)  # Don't go below 0
    
    def get_draft_context(self, player_id: str) -> str:
        """Get draft context string for display"""
        draft_info = self.draft_data.get(player_id)
        if draft_info:
            round_num = draft_info['round']
            pick_no = draft_info['pick_no']
            return f"R{round_num}.{pick_no}"
        return ""

class RosterAnalyzer:
    """Analyze individual team rosters"""
    
    def __init__(self, players_db: Dict, value_analyzer: Optional[PlayerValueAnalyzer] = None):
        self.players_db = players_db
        self.value_analyzer = value_analyzer
        
    def get_player_info(self, player_id: str) -> Dict:
        """Get player information by ID"""
        if player_id in self.players_db:
            return self.players_db[player_id]
        # Handle defense teams (like "BAL", "KC", etc.)
        return {
            'first_name': '',
            'last_name': player_id,
            'position': 'DEF',
            'team': player_id,
            'fantasy_positions': ['DEF']
        }
    
    def analyze_roster(self, roster: Dict) -> Dict:
        """Analyze a single roster for strengths and weaknesses"""
        players = roster.get('players', [])
        starters = roster.get('starters', [])
        
        # Categorize players by position
        positions = defaultdict(list)
        starter_positions = defaultdict(list)
        
        for player_id in players:
            player_info = self.get_player_info(player_id)
            pos = player_info.get('position', 'UNKNOWN')
            player_name = f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip()
            if not player_name:
                player_name = player_id
                
            positions[pos].append({
                'id': player_id,
                'name': player_name,
                'team': player_info.get('team', ''),
                'is_starter': player_id in starters
            })
            
            if player_id in starters:
                starter_positions[pos].append(player_name)
        
        # Analyze positional strength
        analysis = {
            'total_players': len(players),
            'positions': dict(positions),
            'starter_positions': dict(starter_positions),
            'strengths': [],
            'weaknesses': [],
            'needs': []
        }
        
        # Determine strengths and weaknesses
        pos_counts = {pos: len(players) for pos, players in positions.items()}
        
        # Standard roster expectations for redraft leagues
        expected_counts = {
            'QB': 2,
            'RB': 4,
            'WR': 5,
            'TE': 2,
            'K': 1,
            'DEF': 1
        }
        
        for pos, expected in expected_counts.items():
            actual = pos_counts.get(pos, 0)
            if actual > expected + 1:
                analysis['strengths'].append(f"{pos} depth ({actual} players)")
            elif actual < expected:
                analysis['weaknesses'].append(f"{pos} shortage ({actual}/{expected})")
                analysis['needs'].append(pos)
        
        return analysis

class LeagueAnalyzer:
    """Main league analysis class"""
    
    def __init__(self, league_id: str):
        self.league_id = league_id
        self.api = SleeperAPI()
        self.roster_analyzer = None
        
    def load_league_data(self):
        """Load all necessary league data"""
        print(f"Loading league data for ID: {self.league_id}")
        
        # Get league info
        self.league_info = self.api.get_league_info(self.league_id)
        print(f"League: {self.league_info['name']}")
        
        # Get rosters
        self.rosters = self.api.get_league_rosters(self.league_id)
        print(f"Found {len(self.rosters)} teams")
        
        # Get users
        self.users = self.api.get_league_users(self.league_id)
        
        # Create user lookup
        self.user_lookup = {user['user_id']: user for user in self.users}
        
        # Get players database and set up enhanced value analyzer
        players_db = self.api.get_all_players()
        self.value_analyzer = PlayerValueAnalyzer(self.api, players_db, self.league_id)
        self.value_analyzer.load_trending_data()
        
        # Load draft data if available
        draft_id = self.league_info.get('draft_id')
        if draft_id:
            self.value_analyzer.load_draft_data(draft_id)
        
        # Load performance data for enhanced analysis
        self.value_analyzer.load_performance_data()
        
        self.roster_analyzer = RosterAnalyzer(players_db, self.value_analyzer)
        
    def analyze_league(self):
        """Perform complete league analysis"""
        if not self.roster_analyzer:
            self.load_league_data()
            
        print("\n" + "="*60)
        print(f"LEAGUE ANALYSIS: {self.league_info['name']}")
        print("="*60)
        
        team_analyses = []
        seen_roster_ids = set()
        
        for roster in self.rosters:
            roster_id = roster['roster_id']
            owner_id = roster.get('owner_id')
            
            # Skip duplicate rosters
            if roster_id in seen_roster_ids:
                continue
            
            # Skip rosters without owner_id (inactive/orphaned teams)
            if not owner_id:
                continue
                
            seen_roster_ids.add(roster_id)
            
            user_info = self.user_lookup.get(owner_id, {})
            team_name = user_info.get('display_name', f"Team {roster_id}")
            
            # Add team name from metadata if available
            if roster.get('metadata') and roster['metadata'].get('team_name'):
                team_name = roster['metadata']['team_name']
            
            analysis = self.roster_analyzer.analyze_roster(roster)
            analysis['team_name'] = team_name
            analysis['roster_id'] = roster_id
            analysis['owner_info'] = user_info
            
            team_analyses.append(analysis)
            
        # Display team analyses
        for analysis in sorted(team_analyses, key=lambda x: x['roster_id']):
            self.display_team_analysis(analysis)
            
        # Find trade opportunities
        self.find_trade_opportunities(team_analyses)
        
    def display_team_analysis(self, analysis: Dict):
        """Display analysis for a single team with enhanced table format"""
        print(f"\n📊 {analysis['team_name']} (Roster #{analysis['roster_id']})")
        print("-" * 70)
        
        # Collect all player data with values and ADP
        all_players_data = []
        if self.value_analyzer:
            for pos_players in analysis['positions'].values():
                for player in pos_players:
                    value_score = self.value_analyzer.calculate_player_value_score(player['id'])
                    
                    # Get ADP information
                    adp_display = self._get_player_adp_display(player['id'], player['name'])
                    
                    all_players_data.append({
                        'name': player['name'],
                        'position': self._get_player_position(player['id']),
                        'value_score': value_score,
                        'is_starter': player['is_starter'],
                        'player_id': player['id'],
                        'adp_display': adp_display
                    })
        
        # Sort by value to identify top players for highlighting
        all_players_data.sort(key=lambda x: x['value_score'], reverse=True)
        top_player_ids = {p['player_id'] for p in all_players_data[:3]}  # Top 3 get star emoji
        
        # Separate starters and bench players
        starters = [p for p in all_players_data if p['is_starter']]
        bench = [p for p in all_players_data if not p['is_starter']]
        
        # Display starting lineup table
        if starters:
            print("\n🏈 STARTING LINEUP")
            self._display_player_table(starters, top_player_ids)
        
        # Display bench players table
        if bench:
            print("\n📋 BENCH PLAYERS")
            self._display_player_table(bench, top_player_ids)
        
        # Show strengths and weaknesses
        if analysis['strengths']:
            print(f"\n💪 Strengths: {', '.join(analysis['strengths'])}")
        if analysis['weaknesses']:
            print(f"⚠️  Weaknesses: {', '.join(analysis['weaknesses'])}")
        if analysis['needs']:
            print(f"🎯 Needs: {', '.join(analysis['needs'])}")
    
    def _get_player_position(self, player_id: str) -> str:
        """Get player position from the database"""
        if self.roster_analyzer and self.roster_analyzer.players_db:
            player_info = self.roster_analyzer.players_db.get(player_id, {})
            return player_info.get('position', 'UNKNOWN')
        return 'UNKNOWN'
    
    def _get_player_adp_display(self, player_id: str, player_name: str) -> str:
        """Get ADP display string for a player"""
        if not self.value_analyzer:
            return "N/A"
        
        # First try league draft ADP
        draft_context = self.value_analyzer.get_draft_context(player_id)
        if draft_context:
            return draft_context
        
        # Fall back to external ADP with asterisk
        if self.value_analyzer.adp_provider:
            external_adp = self.value_analyzer.adp_provider.get_external_adp(player_name)
            if external_adp:
                # Convert pick number to round.pick format
                round_num = ((external_adp - 1) // 12) + 1
                pick_in_round = ((external_adp - 1) % 12) + 1
                return f"R{round_num}.{pick_in_round:02d}*"
        
        return "Undrafted*"
    
    def _display_player_table(self, players: List[Dict], top_player_ids: set):
        """Display a formatted table of players"""
        if not players:
            return
        
        # Table header
        print("┌─────────┬──────────────────────┬─────────────┬───────┐")
        print("│ Pos     │ Player               │ ADP         │ Value │")
        print("├─────────┼──────────────────────┼─────────────┼───────┤")
        
        # Sort players by position for better organization
        position_order = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
        players.sort(key=lambda x: (position_order.index(x['position']) if x['position'] in position_order else 99, -x['value_score']))
        
        # Table rows
        for player in players:
            pos = player['position']
            name = player['name']
            adp = player['adp_display']
            value = f"{player['value_score']:.1f}"
            
            # Add star emoji for top players - keep consistent field width
            if player['player_id'] in top_player_ids:
                pos_display = f" {pos}⭐"  # Add one space to the left
            else:
                pos_display = pos
            
            # Truncate name if too long
            if len(name) > 20:
                name = name[:17] + "..."
            
            # Use consistent field widths
            print(f"│ {pos_display:<7} │ {name:<20} │ {adp:<11} │ {value:>5} │")
        
        # Table footer
        print("└─────────┴──────────────────────┴─────────────┴───────┘")
    
    def find_trade_opportunities(self, team_analyses: List[Dict]):
        """Identify potential trade opportunities"""
        print("\n" + "="*60)
        print("🔄 TRADE OPPORTUNITIES")
        print("="*60)
        
        # Group teams by needs and strengths
        needs_map = defaultdict(list)
        strengths_map = defaultdict(list)
        
        for analysis in team_analyses:
            team_name = analysis['team_name']
            for need in analysis['needs']:
                needs_map[need].append(team_name)
            for strength in analysis['strengths']:
                # Extract position from strength description
                pos = strength.split()[0]
                strengths_map[pos].append(team_name)
        
        # Find complementary needs
        opportunities = []
        for pos in ['QB', 'RB', 'WR', 'TE']:
            teams_needing = needs_map.get(pos, [])
            teams_with_depth = strengths_map.get(pos, [])
            
            for needy_team in teams_needing:
                for deep_team in teams_with_depth:
                    if needy_team != deep_team:
                        opportunities.append({
                            'position': pos,
                            'team_needing': needy_team,
                            'team_with_depth': deep_team
                        })
        
        if opportunities:
            print("\n🎯 Potential Trade Matches:")
            for opp in opportunities:
                print(f"• {opp['team_needing']} needs {opp['position']} ← → {opp['team_with_depth']} has {opp['position']} depth")
        else:
            print("\n🤔 No obvious trade opportunities found based on positional needs.")
            print("Consider looking at player values and performance for more nuanced trades.")

def main():
    """Main execution function"""
    # Your league ID
    LEAGUE_ID = "1257104566718054400"
    
    try:
        analyzer = LeagueAnalyzer(LEAGUE_ID)
        analyzer.analyze_league()
        
        print("\n" + "="*60)
        print("✅ Analysis complete!")
        print("💡 This is the foundation for trade analysis.")
        print("   Next steps: Add player values, trade proposals, and fairness scoring.")
        print("="*60)
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data from Sleeper API: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
