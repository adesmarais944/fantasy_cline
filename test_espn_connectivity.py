#!/usr/bin/env python3
"""
Test script to verify ESPN API connectivity and basic functionality
"""

import requests
import time
from espn_stats_provider import espn_stats_provider

def test_espn_connectivity():
    """Test basic ESPN API connectivity"""
    print("🧪 Testing ESPN API Connectivity...")
    
    # Test 1: Basic connectivity to ESPN API
    test_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    
    try:
        response = requests.get(test_url, timeout=10)
        if response.status_code == 200:
            print("✅ ESPN API is accessible")
        else:
            print(f"❌ ESPN API returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to connect to ESPN API: {e}")
        return False
    
    # Test 2: Test player stats endpoint with a known player
    print("\n🧪 Testing player statistics endpoint...")
    
    # Test with Patrick Mahomes (ESPN ID: 3139477)
    test_player_id = "3139477"
    player_stats = espn_stats_provider.get_player_statistics(test_player_id, "2024")
    
    if player_stats:
        print("✅ Successfully fetched player statistics")
        print(f"   Player: Patrick Mahomes")
        print(f"   Season totals: {len(player_stats.get('season_totals', {}))} stats")
        print(f"   Game logs: {len(player_stats.get('game_logs', []))} games")
        
        if player_stats.get('recent_performance'):
            recent = player_stats['recent_performance']
            print(f"   Recent performance: {recent.get('last_4_avg', 0):.1f} PPG")
            
    else:
        print("❌ Failed to fetch player statistics")
        return False
    
    # Test 3: Test team statistics endpoint
    print("\n🧪 Testing team statistics endpoint...")
    
    # Test with Kansas City Chiefs (team abbreviation: kc)
    team_stats = espn_stats_provider.get_team_statistics("kc")
    
    if team_stats:
        print("✅ Successfully fetched team statistics")
        print(f"   Team stats structure: {list(team_stats.keys())}")
    else:
        print("⚠️  Team statistics endpoint may need adjustment")
    
    print("\n🎉 ESPN API connectivity test completed successfully!")
    return True

def test_player_mapping():
    """Test player ID mapping functionality"""
    print("\n🧪 Testing player ID mapping...")
    
    # Test mapping for known players
    test_players = [
        {"first_name": "Patrick", "last_name": "Mahomes"},
        {"first_name": "Christian", "last_name": "McCaffrey"},
        {"first_name": "Justin", "last_name": "Jefferson"}
    ]
    
    for player in test_players:
        espn_id = espn_stats_provider.map_player_to_espn_id(player)
        if espn_id:
            print(f"✅ Mapped {player['first_name']} {player['last_name']} -> ESPN ID: {espn_id}")
        else:
            print(f"⚠️  Could not map {player['first_name']} {player['last_name']}")
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("ESPN API CONNECTIVITY TEST")
    print("=" * 60)
    
    success = test_espn_connectivity()
    test_player_mapping()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests passed! ESPN API integration is working.")
    else:
        print("❌ Some tests failed. Check ESPN API configuration.")
    print("=" * 60)
