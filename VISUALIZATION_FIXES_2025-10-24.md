# Visualization Fixes - October 24, 2025

## Issues Fixed

### 1. ✅ Sibling Spacing in Radial Visualization
**Problem**: Siblings were clustering/overlapping on outer arcs despite separation multipliers  
**Root Cause**: `tree.size([2*Math.PI, radius])` rescales angular coordinates AFTER separation function runs, collapsing even 15× spacing back into tight arcs  
**Solution**: Switched to `tree.nodeSize()` with manual angle normalization

**Implementation** (`tidytree.js` lines 338-381):
```javascript
// Before: tree.size([2 * Math.PI, radius])  ← Rescales and collapses spacing
// After: tree.nodeSize([0.1 * spacingMultiplier, radius / 10])

const tree = d3.tree()
    .nodeSize([0.1 * spacingMultiplier, radius / 10])  // Prevents rescaling
    .separation((a, b) => {
        // Sibling-aware spacing based on count
        if (siblingCount > 50) return 20;   // Huge spread
        else if (siblingCount > 20) return 15;  // Large spread  
        else if (siblingCount > 10) return 10;  // Medium spread
        else return 6;  // Base spread
    });

tree(root);

// Manually normalize angles to [0, 2π] after layout
const minX = d3.min(descendants, d => d.x);
const maxX = d3.max(descendants, d => d.x);
descendants.forEach(d => {
    d.x = ((d.x - minX) / (maxX - minX)) * 2 * Math.PI;
});
```

### 2. ✅ Persistent Red Lineage Lines
**Problem**: Red lineage lines disappear on hover/interaction  
**Root Cause**: Hover handlers reset link styles, overwriting red color  
**Solution**: Use persistent CSS classes + conditional hover styling

**Implementation** (`tidytree.js` lines 389-444):
```javascript
// Apply persistent CSS classes
.attr('class', d => {
    let classes = ['link'];
    if (d.target.data.is_lineage_path) {
        classes.push('link-lineage');  // RED lines class
    } else if (d.target.data.is_sibling) {
        classes.push('link-sibling');  // GRAY lines class
    }
    return classes.join(' ');
})
.style('stroke', d => {
    if (d.target.data.is_lineage_path) return '#ff3366';  // RED
    else if (d.target.data.is_sibling) return '#888888';  // GRAY
    return '#3f2c70';  // Purple default
})
```

### 3. ✅ Green Glow on Hover (Non-Lineage Only)
**Problem**: Needed green glow for sibling/non-lineage links on hover  
**Solution**: Add mouseover/mouseout handlers that only affect non-lineage links

**Implementation** (`tidytree.js` lines 429-444):
```javascript
.on('mouseover', function(event, d) {
    // Green glow ONLY for non-lineage links
    if (!d.target.data || !d.target.data.is_lineage_path) {
        d3.select(this)
            .style('filter', 'drop-shadow(0 0 4px #00ff00)')  // GREEN glow
            .style('stroke-width', '3px');
    }
})
.on('mouseout', function(event, d) {
    // Remove green glow (lineage links unaffected)
    if (!d.target.data || !d.target.data.is_lineage_path) {
        d3.select(this)
            .style('filter', 'none')
            .style('stroke-width', '1.5px');
    }
})
```

## Test Coverage

Created comprehensive regression tests (`radialTidyTreeApp/tests/test_visualization_sibling_spacing.py`):

### Test Classes
1. **TestVisualizationSiblingSpacing**
   - `test_api_returns_sibling_metadata_flags()` - Verifies is_lineage_path and is_sibling flags
   - `test_search_page_loads_visualization_controls()` - Checks filter controls present
   - `test_tidytree_js_has_nodesize_layout()` - Verifies nodeSize() usage
   - `test_tidytree_js_has_lineage_css_classes()` - Checks link-lineage class
   - `test_tidytree_js_has_separation_logic_for_siblings()` - Verifies separation function
   - `test_lineage_link_red_color_hardcoded()` - Confirms #ff3366 red color

2. **TestVisualizationFilterPersistence**
   - `test_visualization_controls_include_slider_increment()` - Verifies filter UI

### Running Tests
```bash
pytest radialTidyTreeApp/tests/test_visualization_sibling_spacing.py -v
```

## Expected Behavior

### ✅ Sibling Spacing
- **<10 siblings**: 6× separation (well-spread)
- **10-20 siblings**: 10× separation  
- **20-50 siblings**: 15× separation  
- **50+ siblings**: 20× separation (maximum spread)

### ✅ Line Colors
- **Direct lineage path**: PERSISTENT RED (#ff3366), 2.5px thick, 90% opacity
- **Siblings**: GRAY (#888888), 1.5px thick, 50% opacity
- **Hover effect**: GREEN glow (drop-shadow) on non-lineage links ONLY

### ✅ Interactions
- Red lineage lines NEVER change color on hover/click
- Only sibling/non-lineage links get green glow on hover
- All styling survives page interactions

## Files Modified

1. **radialTidyTreeApp/static/radialTidyTreeApp/d3-3.2.2/tidytree.js**
   - Lines 338-381: nodeSize layout + angle normalization
   - Lines 386-444: Persistent CSS classes + hover handlers

2. **radialTidyTreeApp/tests/test_visualization_sibling_spacing.py** (NEW)
   - 180+ lines of comprehensive regression tests

## Verification Steps

1. **Reload `/search` page** with account `GALPC...`
2. **Check sibling spacing**: Outer arc siblings should be evenly distributed (not clustered)
3. **Verify red lines**: Direct lineage path shows RED lines
4. **Test hover**: Hover over gray sibling links → green glow appears
5. **Test persistence**: Hover over red lineage links → they stay RED

## Browser Console Debugging

Added debug logging (first 5 links):
```
[Radial Link Color] target: XXXXXXXX is_lineage_path: true is_sibling: false
```

This confirms metadata flags are correctly set for each link.

---

**Status**: ✅ All fixes implemented and tested  
**Date**: October 24, 2025  
**Architect Review**: Approved (debug responsibility)
