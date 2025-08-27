#!/usr/bin/env python3
"""
Test script to verify ESPN Stats Provider integration with player mapping
"""

import json
from espn_stats_provider import espn_stats_provider
from sleeper_trade_analyzer import SleeperAPI

def test_player_mapping_and_stats():
    """Test player mapping and statistics fetching"""
    print("🧪 Testing Player Mapping & Statistics Integration")
    print("=" * 60)
    
    sleeper_api = SleeperAPI()
    players_db = sleeper_api.get_all_players()
    
    # Test with known players from our mapping
    test_players = [
        "Patrick Mahomes",
        "Christian McCaffrey", 
        "Justin Jefferson",
        "CeeDee Lamb"
    ]
    
    successful_mappings = 0
    successful_stats = 0
    
    for player_name in test_players:
        print(f"\n🔍 Testing: {player_name}")
        
        # Find player in Sleeper database
        sleeper_player = None
        for player_id, player_data in players_db.items():
            current_name = f"{player_data.get('first_name', '')} {player_data.get('last_name', '')}".strip()
            if current_name == player_name:
                sleeper_player = player_data
                sleeper_player['id'] = player_id
                break
        
        if not sleeper_player:
            print(f"   ❌ Could not find {player_name} in Sleeper database")
            continue
        
        # Test mapping to ESPN ID
        espn_id = espn_stats_provider.map_player_to_espn_id(sleeper_player)
        if espn_id:
            print(f"   ✅ Mapped to ESPN ID: {espn_id}")
            successful_mappings += 1
            
            # Test fetching statistics
            stats = espn_stats_provider.get_player_statistics(espn_id, "2024")
            if stats:
                print(f"   ✅ Successfully fetched statistics")
                print(f"      Season totals: {len(stats.get('season_totals', {}))} stats")
                print(f"      Game logs: {len(stats.get('game_logs', []))} games")
                
                if stats.get('recent_performance'):
                    recent = stats['recent_performance']
                    print(f"      Recent performance: {recent.get('last_4_avg', 0):.1f} PPG")
                
                successful_stats += 1
            else:
                print(f"   ⚠️  Could not fetch statistics (may be off-season)")
        else:
            print(f"   ❌ Could not map to ESPN ID")
    
    print(f"\n📊 Results:")
    print(f"   Successful mappings: {successful_mappings}/{len(test_players)}")
    print(f"   Successful stats fetch: {successful_stats}/{successful_mappings}")
    
    return successful_mappings > 0

def test_mapping_system():
    """Test the complete mapping system"""
    print("\n🧪 Testing Complete Mapping System")
    print("=" * 40)
    
    # Test core mappings
    core_mappings = espn_stats_provider._load_core_mappings()
    cache_mappings = espn_stats_provider._load_cache()
    
    print(f"Core mappings: {len(core_mappings.get('mappings', {}))} players")
    print(f"Cache mappings: {len(cache_mappings.get('mappings', {}))} players")
    
    # Test specific mappings
    test_cases = [
        {"first_name": "Patrick", "last_name": "Mahomes"},
        {"first_name": "Christian", "last_name": "McCaffrey"},
        {"first_name": "CeeDee", "last_name": "Lamb"}
    ]
    
    for test_case in test_cases:
        espn_id = espn_stats_provider.map_player_to_espn_id(test_case)
        if espn_id:
            print(f"✅ {test_case['first_name']} {test_case['last_name']} -> {espn_id}")
        else:
            print(f"❌ {test_case['first_name']} {test_case['last_name']} -> Not mapped")

if __name__ == "__main__":
    print("=" * 60)
    print("📊 ESPN STATS PROVIDER INTEGRATION TEST")
    print("=" * 60)
    
    # Test mapping system
    test_mapping_system()
    
    # Test player mapping and stats
    success = test_player_mapping_and_stats()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Integration test successful! Player mapping system is working.")
        print("💡 Next: Integrate statistics into value calculation")
    else:
        print("❌ Integration test failed. Check player mappings.")
    print("=" * 60)
