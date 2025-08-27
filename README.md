# Fantasy Cline - Player Mapping Refresh Utility

## Overview

The Player Mapping Refresh Utility is a Python script that maintains and updates player ID mappings between Sleeper and ESPN fantasy football platforms. It uses fuzzy matching algorithms to automatically map players and provides tools for manual verification and cleanup.

## Prerequisites

- Python 3.8+
- Required packages (install via `pip install -r requirements.txt`):
  - `requests`
  - `difflib`

## File Structure

### Core Files
- `refresh_mappings.py` - Main refresh utility
- `player_mapping.json` - Manually curated core mappings (high confidence)
- `player_mapping_cache.json` - Auto-generated cache mappings (varying confidence)

### Supporting Files
- `config.json` - Configuration for API endpoints and settings
- `sleeper_trade_analyzer.py` - Sleeper API integration
- `espn_stats_provider.py` - ESPN API integration

## Usage

### Basic Refresh
```bash
python refresh_mappings.py
```
Performs an incremental update, preserving existing mappings and adding new ones.

### Full Refresh
```bash
python refresh_mappings.py --full
```
Performs a complete refresh, replacing all mappings with new matches.

### Interactive Mode
```bash
python refresh_mappings.py --interactive
```
*Note: Interactive mode for manual mapping is planned for future versions.*

## How It Works

### 1. Data Collection
- Fetches current player database from Sleeper API
- Loads ESPN players from core mappings and sample data

### 2. Matching Process
- **Priority Matching**: Exact matches with core mappings first
- **Fuzzy Matching**: Uses sequence matching with position and team validation
- **Confidence Scoring**: Scores from 0.6-1.0 with team bonus (+0.3 for matching teams)

### 3. Confidence Levels
- **Verified**: Exact match with core mapping (score = 1.0)
- **High**: Score > 0.85
- **Medium**: Score > 0.7
- **Low**: Score > 0.6

### 4. Output Files
- Updates `player_mapping_cache.json` with new matches
- Preserves manually curated mappings in `player_mapping.json`

## Configuration

Edit `config.json` to customize:
- API endpoints
- Refresh intervals
- Matching thresholds
- Logging settings

## Troubleshooting

### Common Issues

1. **API Rate Limiting**:
   - The utility includes built-in rate limiting
   - If issues persist, increase delays in the configuration

2. **Missing Players**:
   - Check if players exist in both Sleeper and ESPN databases
   - Verify team abbreviations match between platforms

3. **Low Confidence Matches**:
   - Review matches with confidence "low" in the cache
   - Consider adding high-value players to core mappings manually

### Manual Mapping

For players that don't match automatically:
1. Find their ESPN ID from the ESPN website
2. Add to `player_mapping.json` in the format:
```json
{
  "Player Name": {
    "espn_id": "1234567",
    "position": "RB",
    "team": "DAL"
  }
}
```

## Integration

The refresh utility works with:
- **Waiver Wire Analyzer**: Uses player mappings for roster analysis
- **Trade Analyzer**: Provides player value comparisons
- **Stats Integration**: Bridges Sleeper and ESPN statistical data

## Best Practices

1. **Regular Refreshes**: Run incremental updates weekly during season
2. **Manual Verification**: Review high-value player matches
3. **Backup Core Mappings**: Keep `player_mapping.json` version controlled
4. **Monitor Logs**: Check for API errors or matching issues

## Future Enhancements

- Interactive manual mapping interface
- Bulk import/export functionality
- Historical mapping tracking
- Team/position validation improvements
- Performance optimization for large datasets

## Support

For issues with the refresh utility:
1. Check the console output for error messages
2. Verify API connectivity with test scripts
3. Review the cache file for mapping quality
4. Consult the core mappings for reference data
