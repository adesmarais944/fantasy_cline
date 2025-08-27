#!/usr/bin/env python3
"""
ESPN Stats Provider for Fantasy Football Player Value Analysis

This module extends the ESPNADPProvider to fetch and process player statistics
from ESPN API for enhanced player value calculation.
"""

import requests
import json
import time
from typing import Dict, List, Optional, Any, Union
from collections import defaultdict
import statistics

# Import shared components
from sleeper_trade_analyzer import config, ESPNADPProvider

class ESPNStatsProvider(ESPNADPProvider):
    """Enhanced ESPN provider for player statistics and performance data"""
    
    def __init__(self):
        super().__init__()
        self.player_stats_cache = {}
        self.team_stats_cache = {}
        self.player_id_mapping = {}  # ESPN ID to Sleeper ID mapping
        self.stats_endpoints = config.get_dict("espn_api.stats_endpoints")
    
    def get_player_statistics(self, player_id: str, season: str = "2024") -> Optional[Dict]:
        """Get comprehensive player statistics from ESPN API
        
        Args:
            player_id: ESPN player ID
            season: Season year as string (e.g., "2024")
            
        Returns:
            Dictionary with player statistics or None if not found
        """
        # Check cache first
        cache_key = f"{player_id}_{season}"
        if cache_key in self.player_stats_cache:
            return self.player_stats_cache[cache_key]
        
        if not self.enabled:
            return None
            
        try:
            # Build URL for player stats
            endpoint = self.stats_endpoints.get("player_stats", "/athletes/{playerId}/stats")
            url = f"{self.web_api_url}{endpoint.format(playerId=player_id)}"
            
            # Add season parameter if needed
            params = {"season": season} if season else {}
            
            # Make request with rate limiting
            time.sleep(self.rate_limit_delay)
            response = self.session.get(url, params=params, timeout=self.session.timeout)
            response.raise_for_status()
            
            stats_data = response.json()
            
            # Process and cache the data
            processed_stats = self._process_player_stats(stats_data, season)
            self.player_stats_cache[cache_key] = processed_stats
            
            return processed_stats
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching ESPN player stats for {player_id}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error processing ESPN stats for {player_id}: {e}")
            return None
    
    def _process_player_stats(self, stats_data: Dict, season: str) -> Dict:
        """Process raw ESPN stats data into standardized format"""
        if not stats_data:
            return {}
            
        processed = {
            'season': season,
            'career_totals': {},
            'season_totals': {},
            'game_logs': [],
            'recent_performance': {},
            'consistency_metrics': {}
        }
        
        try:
            # Extract career totals
            if 'career' in stats_data and 'totals' in stats_data['career']:
                processed['career_totals'] = self._extract_fantasy_relevant_stats(
                    stats_data['career']['totals']
                )
            
            # Extract season totals and game logs
            if 'seasons' in stats_data:
                for season_data in stats_data['seasons']:
                    if str(season_data.get('year')) == season:
                        # Season totals
                        if 'totals' in season_data:
                            processed['season_totals'] = self._extract_fantasy_relevant_stats(
                                season_data['totals']
                            )
                        
                        # Game logs
                        if 'games' in season_data:
                            game_logs = []
                            for game in season_data['games']:
                                if 'stats' in game:
                                    game_stats = self._extract_fantasy_relevant_stats(game['stats'])
                                    game_logs.append({
                                        'week': game.get('number', 0),
                                        'stats': game_stats,
                                        'opponent': game.get('opponent', {}).get('abbreviation', ''),
                                        'result': game.get('result', '')
                                    })
                            processed['game_logs'] = game_logs
            
            # Calculate recent performance and consistency
            if processed['game_logs']:
                self._calculate_performance_metrics(processed)
                
        except Exception as e:
            print(f"Error processing stats data: {e}")
            
        return processed
    
    def _extract_fantasy_relevant_stats(self, stats_list: List[Dict]) -> Dict:
        """Extract fantasy-relevant statistics from ESPN stats format"""
        relevant_stats = {}
        
        if not stats_list:
            return relevant_stats
            
        # Map ESPN stat names to standardized names
        stat_mapping = {
            'passingYards': 'pass_yds',
            'passingTouchdowns': 'pass_tds',
            'passingInterceptions': 'pass_int',
            'rushingYards': 'rush_yds',
            'rushingTouchdowns': 'rush_tds',
            'receivingYards': 'rec_yds',
            'receivingTouchdowns': 'rec_tds',
            'receptions': 'receptions',
            'targets': 'targets',
            'fumblesLost': 'fumbles_lost',
            'fieldGoalsMade': 'fg_made',
            'fieldGoalsAttempted': 'fg_attempted',
            'extraPointsMade': 'xp_made',
            'extraPointsAttempted': 'xp_attempted'
        }
        
        for stat in stats_list:
            name = stat.get('name', '')
            value = stat.get('value', 0)
            
            if name in stat_mapping:
                relevant_stats[stat_mapping[name]] = float(value)
                
        return relevant_stats
    
    def _calculate_performance_metrics(self, processed_stats: Dict):
        """Calculate performance metrics from game logs"""
        game_logs = processed_stats['game_logs']
        
        if not game_logs:
            return
            
        # Calculate fantasy points from stats (simplified - would use league scoring)
        fantasy_points = []
        for game in game_logs:
            stats = game['stats']
            points = 0
            
            # Basic fantasy point calculation (adjust based on league settings)
            points += stats.get('pass_yds', 0) / 25
            points += stats.get('pass_tds', 0) * 6
            points -= stats.get('pass_int', 0) * 2
            points += stats.get('rush_yds', 0) / 10
            points += stats.get('rush_tds', 0) * 6
            points += stats.get('rec_yds', 0) / 10
            points += stats.get('rec_tds', 0) * 6
            points += stats.get('receptions', 0) * 0.5  # PPR
            points -= stats.get('fumbles_lost', 0) * 2
            
            fantasy_points.append(points)
        
        # Recent performance (last 4 weeks)
        recent_games = min(4, len(fantasy_points))
        if recent_games > 0:
            recent_avg = sum(fantasy_points[-recent_games:]) / recent_games
            season_avg = sum(fantasy_points) / len(fantasy_points) if fantasy_points else 0
            
            processed_stats['recent_performance'] = {
                'last_4_avg': recent_avg,
                'season_avg': season_avg,
                'trend': recent_avg - season_avg if season_avg > 0 else 0
            }
        
        # Consistency metrics
        if len(fantasy_points) >= 4:
            processed_stats['consistency_metrics'] = {
                'std_dev': statistics.stdev(fantasy_points) if len(fantasy_points) > 1 else 0,
                'min_score': min(fantasy_points),
                'max_score': max(fantasy_points),
                'boom_bust_ratio': (max(fantasy_points) - min(fantasy_points)) / 
                                  (statistics.mean(fantasy_points) if fantasy_points else 1)
            }
    
    def get_team_statistics(self, team_id: str) -> Optional[Dict]:
        """Get team statistics for strength of schedule analysis"""
        cache_key = f"team_{team_id}"
        if cache_key in self.team_stats_cache:
            return self.team_stats_cache[cache_key]
        
        if not self.enabled:
            return None
            
        try:
            endpoint = self.stats_endpoints.get("team_stats", "/teams/{teamId}/statistics")
            url = f"{self.base_url}{endpoint.format(teamId=team_id)}"
            
            time.sleep(self.rate_limit_delay)
            response = self.session.get(url, timeout=self.session.timeout)
            response.raise_for_status()
            
            team_data = response.json()
            processed_team_stats = self._process_team_stats(team_data)
            self.team_stats_cache[cache_key] = processed_team_stats
            
            return processed_team_stats
            
        except Exception as e:
            print(f"Error fetching team stats for {team_id}: {e}")
            return None
    
    def _process_team_stats(self, team_data: Dict) -> Dict:
        """Process team statistics data"""
        # This would extract relevant team offensive metrics
        # For now, return basic structure
        return {
            'offensive_ranking': 0,  # Would calculate based on yards/points
            'points_per_game': 0,
            'yards_per_game': 0,
            'pass_offense_rank': 0,
            'rush_offense_rank': 0
        }
    
    def map_player_to_espn_id(self, sleeper_player_info: Dict) -> Optional[str]:
        """Map Sleeper player to ESPN ID using name matching"""
        # This is a simplified implementation - would need proper player ID mapping
        player_name = f"{sleeper_player_info.get('first_name', '')} {sleeper_player_info.get('last_name', '')}".strip().lower()
        
        # Simple name mapping for common players (would need comprehensive mapping)
        name_to_espn_id = {
            'patrick mahomes': '3139477',
            'christian mccaffrey': '3916387',
            'justin jefferson': '4361544',
            'travis kelce': '2577417',
            'josh allen': '3916386'
        }
        
        return name_to_espn_id.get(player_name)

# Create global instance for easy import
espn_stats_provider = ESPNStatsProvider()
