# EHX Processing Cache Concept

## Overview

This document outlines a performance optimization concept for the Vold.py EHX processing application. The idea is to implement intelligent caching of processed EHX file data to dramatically speed up loading of files that have already been processed.

## Current Processing Flow

1. User double-clicks EHX file in the file list
2. Script parses entire XML file (potentially thousands of panels/materials)
3. Extracts panel data, material breakdowns, and creates structured data
4. Writes log files (`expected.log`, `materials.log`, etc.) to LOG subdirectory
5. Displays results in GUI

**Time**: 10-60+ seconds for large files

## Proposed Caching Flow

### First-Time Processing (Cache Miss)
```
EHX File → XML Parsing → Data Extraction → Create Cache → Write Logs → Display
```

### Subsequent Loads (Cache Hit)
```
EHX File → Check Cache Validity → Load from Cache → Display
```

**Time**: 1-2 seconds for cached files

## Cache Structure

### Location
```
Script/LOG/ehx_cache/
├── cache_index.json          # Master cache registry
├── file_hash_data.json       # Cached processed data
├── file_hash_metadata.json   # File validation info
```

### Cache Index Format
```json
{
  "version": "1.0",
  "entries": {
    "C:\\path\\to\\file.ehx": {
      "cache_file": "abc123_data.json",
      "metadata_file": "abc123_metadata.json",
      "created": "2025-10-31T10:30:00Z",
      "last_accessed": "2025-10-31T14:45:00Z",
      "file_size": 2457600,
      "file_modified": "2025-10-30T09:15:00Z",
      "panels_count": 45,
      "materials_count": 234
    }
  }
}
```

### Cached Data Format
```json
{
  "panels": {
    "panel_guid_1": {
      "name": "Panel A",
      "guid": "panel_guid_1",
      "materials": [...],
      "specs": {...}
    }
  },
  "materials_map": {
    "panel_name": [
      {
        "FamilyMember": 32,
        "Description": "2x6 SPF",
        "Length": "8'-0\"",
        "Quantity": 12
      }
    ]
  },
  "levels": {...},
  "bundles": {...}
}
```

### Metadata Format
```json
{
  "ehx_path": "C:\\path\\to\\file.ehx",
  "file_hash": "abc123def456",
  "file_size": 2457600,
  "file_modified": "2025-10-30T09:15:00Z",
  "processing_version": "1.0",
  "panels_count": 45,
  "materials_count": 234,
  "cache_created": "2025-10-31T10:30:00Z",
  "script_version": "Vold.py v2.1"
}
```

## Implementation Strategy

### 1. Cache Key Generation
```python
import hashlib
import os

def generate_cache_key(ehx_path):
    """Generate unique cache key from file path and content"""
    file_stat = os.stat(ehx_path)
    content_hash = hashlib.md5()

    # Hash file path + modification time + size for uniqueness
    key_data = f"{ehx_path}|{file_stat.st_mtime}|{file_stat.st_size}"
    content_hash.update(key_data.encode())

    return content_hash.hexdigest()[:16]  # 16 char key
```

### 2. Cache Validation Logic
```python
def is_cache_valid(ehx_path, metadata):
    """Check if cached data is still valid"""
    if not os.path.exists(ehx_path):
        return False

    current_stat = os.stat(ehx_path)

    # Check file still exists and hasn't been modified
    return (current_stat.st_size == metadata['file_size'] and
            current_stat.st_mtime == metadata['file_modified'])
```

### 3. Loading Logic Integration
```python
def process_ehx_file_with_cache(full_path, folder_path):
    """Enhanced EHX processing with caching"""

    cache_key = generate_cache_key(full_path)
    cache_data_file = f"LOG/ehx_cache/{cache_key}_data.json"
    cache_meta_file = f"LOG/ehx_cache/{cache_key}_metadata.json"

    # Check for valid cache
    if (os.path.exists(cache_data_file) and
        os.path.exists(cache_meta_file)):

        try:
            with open(cache_meta_file, 'r') as f:
                metadata = json.load(f)

            if is_cache_valid(full_path, metadata):
                # CACHE HIT - Load from cache
                with open(cache_data_file, 'r') as f:
                    cached_data = json.load(f)

                status_val.config(text="Loading from cache...")
                # Process cached data directly
                complete_file_processing(
                    cached_data['panels'],
                    cached_data['materials_map'],
                    full_path, folder_path
                )
                return
        except Exception:
            # Cache corrupted, fall through to normal processing
            pass

    # CACHE MISS - Process normally and create cache
    status_val.config(text="Processing file...")
    # ... existing processing logic ...

    # After successful processing, save to cache
    try:
        cache_data = {
            'panels': panels_by_name,
            'materials_map': panel_materials_map,
            'levels': extracted_levels,
            'bundles': extracted_bundles
        }

        metadata = {
            'ehx_path': full_path,
            'file_hash': cache_key,
            'file_size': os.path.getsize(full_path),
            'file_modified': os.path.getmtime(full_path),
            'processing_version': '1.0',
            'panels_count': len(panels_by_name),
            'materials_count': sum(len(mats) for mats in panel_materials_map.values()),
            'cache_created': datetime.now().isoformat(),
            'script_version': 'Vold.py v2.1'
        }

        # Save cache files
        os.makedirs('LOG/ehx_cache', exist_ok=True)
        with open(cache_data_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
        with open(cache_meta_file, 'w') as f:
            json.dump(metadata, f, indent=2)

    except Exception:
        # Don't fail if caching fails
        pass
```

## Benefits

### Performance Improvements
- **First load**: Same as current (10-60+ seconds)
- **Subsequent loads**: 1-2 seconds (10-50x speedup)
- **Memory usage**: Reduced for repeat loads
- **CPU usage**: Minimal for cached loads

### User Experience
- **Instant loading** for frequently-used files
- **Faster iteration** during development/testing
- **Reduced waiting time** in production workflows

### Technical Benefits
- **Backwards compatible**: Falls back to normal processing
- **Robust validation**: Multiple cache invalidation checks
- **Self-healing**: Corrupted cache auto-regenerates
- **Version aware**: Can invalidate cache on script updates

## Implementation Considerations

### Cache Invalidation Triggers
1. **File modification**: EHX file changed on disk
2. **File moved/renamed**: Path change invalidates cache
3. **Script updates**: Version changes can clear cache
4. **Manual clear**: User option to clear all caches

### Storage Management
- **Auto-cleanup**: Remove caches for deleted files
- **Size limits**: Optional cache size limits
- **Compression**: Could compress large cache files
- **Backup safety**: Cache is disposable, never critical data

### Error Handling
- **Graceful degradation**: Cache failures don't break functionality
- **Logging**: Cache hits/misses logged for performance monitoring
- **Recovery**: Automatic cache regeneration on corruption

### Security Considerations
- **Local only**: Cache contains no sensitive data
- **Path validation**: Ensure cache keys can't access unauthorized files
- **Cleanup**: Old caches don't persist indefinitely

## Performance Metrics

### Expected Speedups
- **Small files** (< 500KB): 5-10x faster
- **Medium files** (500KB-2MB): 10-20x faster
- **Large files** (> 2MB): 20-50x faster

### Cache Hit Scenarios
- **Development**: High hit rate (80-90%) - same files processed repeatedly
- **Production**: Medium hit rate (30-60%) - mix of new and repeat files
- **One-off processing**: Low hit rate (0-10%) - mostly new files

## Future Enhancements

### Advanced Features
1. **Partial caching**: Cache individual panels/components
2. **Incremental updates**: Update only changed parts of files
3. **Network caching**: Share caches across team members
4. **Compression**: Reduce cache file sizes
5. **Prefetching**: Cache recently used files in background

### Monitoring & Analytics
1. **Cache statistics**: Hit rates, storage usage, performance metrics
2. **Usage patterns**: Identify frequently accessed files
3. **Performance tracking**: Monitor actual speedups achieved

## Implementation Priority

### Phase 1: Core Caching
- Basic cache structure and validation
- File modification time checking
- JSON serialization of processed data
- Error handling and fallback logic

### Phase 2: Optimization
- Cache compression
- Size limits and cleanup
- Performance monitoring
- Advanced validation (file hashing)

### Phase 3: Advanced Features
- Partial caching
- Network synchronization
- Predictive prefetching
- Cache analytics dashboard

## Risk Assessment

### Low Risk
- **Backwards compatibility**: Feature is opt-in, doesn't break existing functionality
- **Data integrity**: Cache is derived data, original EHX files remain untouched
- **Performance**: Only improves performance, never degrades it

### Mitigation Strategies
- **Thorough testing**: Extensive testing with various EHX file types
- **Gradual rollout**: Can enable/disable caching via configuration
- **Monitoring**: Track cache performance and error rates
- **User control**: Option to disable caching if issues arise

## Conclusion

This caching concept offers significant performance improvements for EHX processing workflows, especially for users who frequently work with the same files. The implementation is straightforward, backwards-compatible, and provides substantial user experience benefits with minimal risk.

The core concept leverages existing log file infrastructure while adding intelligent cache management to dramatically reduce loading times for repeat file processing.