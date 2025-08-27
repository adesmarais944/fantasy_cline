#!/usr/bin/env python3
"""
Player Mapping Refresh Utility

This script helps refresh and maintain player ID mappings between Sleeper and ESPN.
It provides easy refresh capabilities with fuzzy matching and confidence scoring.
"""

import json
import argparse
import difflib
from typing import Dict, List, Optional, Any
from collections import defaultdict
import requests
import time

# Import existing components
from sleeper_trade_analyzer import config, SleeperAPI
from espn_stats_provider import espn_stats_provider

class PlayerMappingRefresher:
    """Refresh and maintain player ID mappings between Sleeper and ESPN"""
    
    def __init__(self):
        self.sleeper_api = SleeperAPI()
        self.core_mappings_file = "player_mapping.json"
        self.cache_file = "player_mapping_cache.json"
        self.core_mappings = self._load_core_mappings()
        self.cache = self._load_cache()
        
    def _load_core_mappings(self) -> Dict:
        """Load core manually curated mappings"""
        try:
            with open(self.core_mappings_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"version": "1.0", "mappings": {}, "metadata": {}}
    
    def _load_cache(self) -> Dict:
        """Load auto-generated cache"""
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"version": "1.0", "mappings": {}, "metadata": {}}
    
    def _save_cache(self, cache_data: Dict):
        """Save cache to file"""
        with open(self.cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
    
    def fetch_sleeper_players(self) -> Dict:
        """Fetch current Sleeper player database"""
        print("📋 Fetching Sleeper players...")
        players = self.sleeper_api.get_all_players()
        print(f"   Found {len(players)} players in Sleeper database")
        return players
    
    def fetch_espn_players(self) -> List[Dict]:
        """Fetch ESPN players from our core mappings and sample data"""
        print("📋 Loading ESPN players from core mappings...")
        
        # Start with players from our core mappings
        espn_players = []
        
        for name, mapping in self.core_mappings.get('mappings', {}).items():
            espn_players.append({
                "name": name,
                "espn_id": mapping['espn_id'],
                "position": mapping['position'],
                "team": mapping['team']
            })
        
        # Add some additional sample players for testing
        additional_players = [
            {"name": "Amon-Ra St. Brown", "espn_id": "4361548", "position": "WR", "team": "DET"},
            {"name": "Bijan Robinson", "espn_id": "4431882", "position": "RB", "team": "ATL"},
            {"name": "Garrett Wilson", "espn_id": "4430520", "position": "WR", "team": "NYJ"},
            {"name": "Chris Olave", "espn_id": "4430521", "position": "WR", "team": "NO"},
            {"name": "T.J. Hockenson", "espn_id": "3918449", "position": "TE", "team": "MIN"}
        ]
        
        espn_players.extend(additional_players)
        print(f"   Loaded {len(espn_players)} ESPN players from mappings")
        return espn_players
    
    def fuzzy_match_players(self, sleeper_players: Dict, espn_players: List[Dict]) -> Dict:
        """Perform fuzzy matching between Sleeper and ESPN players"""
        print("🔍 Performing fuzzy matching...")
        
        matches = {}
        unmatched = []
        
        # Filter for only skill position players (QB, RB, WR, TE)
        skill_positions = {'QB', 'RB', 'WR', 'TE'}
        sleeper_skill_players = {
            player_id: player_data 
            for player_id, player_data in sleeper_players.items()
            if player_data.get('position') in skill_positions
        }
        
        # Get core player names for prioritization
        core_player_names = set(self.core_mappings.get('mappings', {}).keys())
        
        # First pass: Process ALL players that are in core mappings
        matched_core_players = 0
        for sleeper_id, sleeper_data in sleeper_skill_players.items():
            sleeper_name = f"{sleeper_data.get('first_name', '')} {sleeper_data.get('last_name', '')}".strip()
            
            # Skip if no name or team
            if not sleeper_name or not sleeper_data.get('team'):
                continue
                
            # Exact match with core mappings
            if sleeper_name in core_player_names:
                core_mapping = self.core_mappings['mappings'][sleeper_name]
                matches[sleeper_name] = {
                    "sleeper_id": sleeper_id,
                    "espn_id": core_mapping['espn_id'],
                    "position": sleeper_data.get('position', ''),
                    "team": sleeper_data.get('team', ''),
                    "confidence": "verified",
                    "match_score": 1.0
                }
                matched_core_players += 1
                
        print(f"   Exactly matched {matched_core_players} core players")
        
        # Second pass: Process remaining players with fuzzy matching (no limit)
        processed_count = 0
        for sleeper_id, sleeper_data in sleeper_skill_players.items():
            sleeper_name = f"{sleeper_data.get('first_name', '')} {sleeper_data.get('last_name', '')}".strip()
            sleeper_pos = sleeper_data.get('position', '')
            sleeper_team = sleeper_data.get('team', '')
            
            # Skip if already matched or missing data
            if not sleeper_name or not sleeper_team or sleeper_name in matches:
                continue
            
            best_match = None
            best_score = 0
            
            for espn_player in espn_players:
                espn_name = espn_player['name']
                espn_pos = espn_player['position']
                espn_team = espn_player['team']
                
                # Position must match
                if sleeper_pos != espn_pos:
                    continue
                
                # Calculate name similarity
                similarity = difflib.SequenceMatcher(
                    None, 
                    sleeper_name.lower(), 
                    espn_name.lower()
                ).ratio()
                
                # Team similarity bonus (more important)
                team_bonus = 0.3 if sleeper_team == espn_team else 0
                total_score = similarity + team_bonus
                
                if total_score > best_score and total_score > 0.6:  # Lower threshold to 60%
                    best_score = total_score
                    best_match = espn_player
            
            if best_match:
                confidence = "high" if best_score > 0.85 else "medium" if best_score > 0.7 else "low"
                
                matches[sleeper_name] = {
                    "sleeper_id": sleeper_id,
                    "espn_id": best_match['espn_id'],
                    "position": sleeper_pos,
                    "team": sleeper_team,
                    "confidence": confidence,
                    "match_score": round(best_score, 3)
                }
            else:
                unmatched.append({
                    "sleeper_id": sleeper_id,
                    "name": sleeper_name,
                    "position": sleeper_pos,
                    "team": sleeper_team
                })
            
            processed_count += 1
            if processed_count % 500 == 0:
                print(f"   Processed {processed_count} players...")
        
        print(f"   Matched {len(matches)} players, {len(unmatched)} unmatched")
        return {"matches": matches, "unmatched": unmatched}
    
    def generate_diff_report(self, new_matches: Dict) -> Dict:
        """Generate diff report between current cache and new matches"""
        print("� Generating diff report...")
        
        current_mappings = self.cache.get('mappings', {})
        new_mappings = new_matches.get('matches', {})
        
        added = {}
        updated = {}
        removed = {}
        
        # Find added mappings
        for name, mapping in new_mappings.items():
            if name not in current_mappings:
                added[name] = mapping
        
        # Find updated mappings (different ESPN ID)
        for name, new_mapping in new_mappings.items():
            if name in current_mappings:
                current_mapping = current_mappings[name]
                if new_mapping['espn_id'] != current_mapping.get('espn_id'):
                    updated[name] = {
                        "old": current_mapping,
                        "new": new_mapping
                    }
        
        # Find removed mappings (no longer in new matches)
        for name in current_mappings:
            if name not in new_mappings:
                removed[name] = current_mappings[name]
        
        return {
            "added": added,
            "updated": updated,
            "removed": removed,
            "unmatched": new_matches.get('unmatched', [])
        }
    
    def refresh_mappings(self, full_refresh: bool = False):
        """Refresh player mappings"""
        print("🔄 Refreshing player mappings...")
        print("=" * 60)
        
        # Fetch current player data
        sleeper_players = self.fetch_sleeper_players()
        espn_players = self.fetch_espn_players()
        
        # Perform fuzzy matching
        new_matches = self.fuzzy_match_players(sleeper_players, espn_players)
        
        # Generate diff report
        diff_report = self.generate_diff_report(new_matches)
        
        # Update cache
        if full_refresh or not self.cache.get('mappings'):
            # Full refresh - replace everything
            self.cache = {
                "version": "1.0",
                "last_refreshed": time.strftime("%Y-%m-%d"),
                "mappings": new_matches['matches'],
                "metadata": {
                    "total_matched": len(new_matches['matches']),
                    "total_unmatched": len(new_matches['unmatched']),
                    "refresh_type": "full"
                }
            }
        else:
            # Incremental update - merge with existing
            current_mappings = self.cache.get('mappings', {})
            current_mappings.update(new_matches['matches'])
            self.cache['mappings'] = current_mappings
            self.cache['last_refreshed'] = time.strftime("%Y-%m-%d")
            self.cache['metadata']['refresh_type'] = "incremental"
        
        # Save updated cache
        self._save_cache(self.cache)
        
        # Display results
        self._display_results(diff_report)
        
        return diff_report
    
    def _display_results(self, diff_report: Dict):
        """Display refresh results"""
        print("\n📈 REFRESH RESULTS:")
        print("=" * 40)
        
        print(f"✅ Added: {len(diff_report['added'])} players")
        print(f"🔄 Updated: {len(diff_report['updated'])} players")
        print(f"❌ Removed: {len(diff_report['removed'])} players")
        print(f"❓ Unmatched: {len(diff_report['unmatched'])} players")
        
        # Show sample of added players
        if diff_report['added']:
            print("\n🎯 Newly Matched Players (sample):")
            for name, mapping in list(diff_report['added'].items())[:5]:
                print(f"   {name} ({mapping['position']} - {mapping['team']}) - Confidence: {mapping['confidence']}")
        
        # Show sample of unmatched players
        if diff_report['unmatched']:
            print("\n⚠️  Unmatched Players (sample):")
            for player in diff_report['unmatched'][:5]:
                print(f"   {player['name']} ({player['position']} - {player['team']})")
        
        print(f"\n💾 Cache updated: {self.cache_file}")
        print("🔄 Refresh complete!")
    
    def interactive_mode(self):
        """Interactive mode for manual mapping"""
        print("🎮 Starting interactive mode...")
        print("This feature would allow manual mapping of unmatched players")
        print("Interactive mode coming in future version!")
        # Implementation would show unmatched players and allow manual mapping

def main():
    """Main function for refresh utility"""
    parser = argparse.ArgumentParser(description="Refresh player ID mappings between Sleeper and ESPN")
    parser.add_argument("--full", action="store_true", help="Perform full refresh (replace all mappings)")
    parser.add_argument("--update", action="store_true", help="Perform incremental update (default)")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode for manual mapping")
    
    args = parser.parse_args()
    
    refresher = PlayerMappingRefresher()
    
    if args.interactive:
        refresher.interactive_mode()
    else:
        # Default to incremental update unless --full is specified
        full_refresh = args.full
        refresher.refresh_mappings(full_refresh=full_refresh)

if __name__ == "__main__":
    print("=" * 60)
    print("🔄 PLAYER MAPPING REFRESH UTILITY")
    print("=" * 60)
    
    main()
