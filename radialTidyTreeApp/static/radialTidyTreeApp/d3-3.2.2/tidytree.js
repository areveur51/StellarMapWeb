/*
Debug variables that capture data at various points
 */
let data, hData, links, nodes, rootnode;

/*
Globals
 */

const dataURI = "";
let hierarchy = {};
let chart;

//Sizing
let margin = ({top: 30, right: 60, bottom: 30, left: 30});
const viewportWidth = window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth;
const viewportHeight = window.innerHeight || document.documentElement.clientHeight || document.body.clientHeight;

let dy = viewportWidth / 6;
let dx = 20;
let tree = d3.tree().nodeSize([dx, dy]);
let diagonal = d3.linkHorizontal()
    .x(d => d.y)
    .y(d => d.x);

/*
Chart Options
 */


const initialDepth = 0; // Nodes with depth greater than this value are initially hidden
const animationDuration = 250;  // Time in ms to animate update

/*
End Chart Options
 */

// Fixed standard sizes following Mike Bostock's canonical pattern
const RADIAL_NODE_SIZE = 9;  // Fixed node circle radius (px)
const RADIAL_TEXT_SIZE = 17; // Fixed text font size (px)
const RADIAL_COMPACTNESS = 0.5;  // Depth multiplier to shorten child lines (0.5 = 50% shorter)

/*
End Globals
 */

/*
Initial run
 */

// DISABLED: Automatic JSON loading causes parsing errors when dataURI is empty
// We now use the renderRadialTree function instead for controlled data rendering

// d3.json(dataURI, {
//     crossOrigin: "anonymous"
// })
//     .then((json) => {
//         data = json;  //data has json in initial state
//         return json;
//     })
//     .then((json) => {
//         return levelNodes(json);
//     })
//     .then((result) => {
//         hData = result; //captures that flat array levelNodes returns
//         return result
//     })
//     .then((result) => {
//         hData = d3.stratify()(result);
//         chart = makeTree(hData);  //keep chart reference around for updates
//         document.querySelector("body").appendChild(chart);
//     });

// preprocess json data
function levelNodes(data) {
    return new Promise((resolve) => {

        hierarchy["Root"] = {
            id: "0",
            parentId: undefined,
            weight: 1,
            name: "",
        };

        data.forEach(function (link) {
            if (link.child_id !== 0) {
                hierarchy[link.child_id] = {
                    id: link.child_id,
                    name: link.child,
                    parentId: link.parent,
                    weight: link.child_weight || 1,
                    parent_weight: link.parent_weight,
                    parent_level: link.parent_level
                }
            }

        });
        resolve(Object.values(hierarchy));
    })
}

function makeTree(data) {
    const root = d3.hierarchy(data);
    rootnode = root;  //capture root in rootnode
    root.x0 = dy / 2;
    root.y0 = 0;

    // A hidden node has its children stored in _children

    root.descendants().forEach((d, i) => {
        d._id = i;
        d._children = d.children;
        if (d.depth > initialDepth) d.children = null;
    });

    const svg = d3.create("svg")
        .attr("viewBox", [-margin.left, -margin.top, viewportWidth, dx])      // min-x, min-y, width, height
        .style("font", "10px sans-serif")
        .style("user-select", "none");

    const gLink = svg.append("g")
        .attr("fill", "none")
        .attr("stroke", "#555")
        .attr("stroke-opacity", 0.4)
        .attr("stroke-width", 1.5);

    const gNode = svg.append("g")
        .attr("cursor", "pointer")
        .attr("pointer-events", "all");

    function update(source) {

        const duration = d3.event && d3.event.altKey ? (animationDuration * 10) : animationDuration; // Slow animation by Alt + Clicking
        const nodes = root.descendants().reverse();
        const links = root.links();

        // Compute the new tree layout.
        tree(root);

        let left = root;
        let right = root;
        let up = root;

        // find the left-most, right-most, etc points
        // this is probably more efficient than calling reduce multiple times
        root.eachBefore(node => {
            if (node.x < left.x) left = node;
            if (node.x > right.x) right = node;
            if (node.y > up.y) up = node;
        });

        const chartHeight = right.x - left.x + margin.top + margin.bottom;
        const _chartWidth = up.y + margin.left + margin.right;
        const chartWidth = _chartWidth > viewportWidth ? _chartWidth : viewportWidth;
        console.log(_chartWidth);
        console.log(chartWidth);

        const transition = svg.transition()
            .duration(duration)
            .attr("viewBox", [-margin.left, left.x - margin.top, chartWidth, chartHeight])
            .tween("resize", window.ResizeObserver ? null : () => () => svg.dispatch("toggle"));

        // Update the nodes…
        const node = gNode.selectAll("g")
            .data(nodes, d => d._id);

        // Enter any new nodes at the parent's previous position.
        const nodeEnter = node.enter().append("g")
            .attr("transform", d => `translate(${source.y0},${source.x0})`)
            .attr("fill-opacity", 0)
            .attr("stroke-opacity", 0)
            .on("click", (event, d) => {
                d.children = d.children ? null : d._children;
                update(d)

            });

        nodeEnter.append("circle")
            .attr("r", RADIAL_NODE_SIZE)
            .attr("fill", d => d._children ? "#555" : "#999")
            .attr("class", d => "depth_" + d.depth);


        nodeEnter.append("text")
            .attr("dy", "0.31em")
            .attr("x", d => d._children ? -6 : 6)
            .attr("text-anchor", d => d._children ? "end" : "start")
            .style("font-size", RADIAL_TEXT_SIZE + "px")
            .text(d => d.data.data.name)
            .clone(true).lower()
            .attr("stroke-linejoin", "round")
            .attr("stroke-width", 3)
            .attr("stroke", "white");

        // Transition nodes to their new position.
        const nodeUpdate = node.merge(nodeEnter).transition(transition)
            .attr("transform", d => `translate(${d.y},${d.x})`)
            .attr("fill-opacity", 1)
            .attr("stroke-opacity", 1);

        // Transition exiting nodes to the parent's new position.
        const nodeExit = node.exit().transition(transition).remove()
            .attr("transform", d => `translate(${source.y},${source.x})`)
            .attr("fill-opacity", 0)
            .attr("stroke-opacity", 0);

        // Update the links…
        const link = gLink.selectAll("path")
            .data(links, d => d.target._id);

        // Enter any new links at the parent's previous position.
        const linkEnter = link.enter().append("path")
            .attr("d", d => {
                const o = {
                    x: source.x0,
                    y: source.y0
                };
                return diagonal({
                    source: o,
                    target: o
                });
            });

        // Transition links to their new position.
        link.merge(linkEnter).transition(transition)
            .attr("d", diagonal);

        // Transition exiting nodes to the parent's new position.
        link.exit().transition(transition).remove()
            .attr("d", d => {
                const o = {
                    x: source.x,
                    y: source.y
                };
                return diagonal({
                    source: o,
                    target: o
                });
            });

        // Stash the old positions for transition.
        root.eachBefore(d => {
            d.x0 = d.x;
            d.y0 = d.y;
        });


    }

    update(root);

    return svg.node();
}

// Global function to render radial tree with data
function renderRadialTree(jsonData) {
    try {
        // Store data globally so slider can re-render
        window.currentTreeData = jsonData;
        
        const existingSvg = document.querySelector('#tree');
        if (existingSvg) {
            existingSvg.innerHTML = '';
        }

        let processedData;
        if (jsonData && typeof jsonData === 'object') {
            if (jsonData.name || jsonData.children || jsonData.stellar_account) {
                processedData = jsonData;
            } else {
                processedData = {
                    name: jsonData.stellar_account || 'Root Node',
                    node_type: jsonData.node_type || 'ACCOUNT',
                    created: jsonData.created || new Date().toISOString(),
                    children: jsonData.children || []
                };
            }
        } else {
            processedData = {
                name: 'Sample Root',
                node_type: 'ACCOUNT',
                created: '2015-09-30 13:15:54',
                children: []
            };
        }

        console.log('Processing tree data:', processedData);

        // Pre-analyze tree to calculate optimal radius where nodes TOUCH but DON'T OVERLAP
        const tempRoot = d3.hierarchy(processedData);
        const tempDescendants = tempRoot.descendants();
        
        // Count nodes at each depth level
        const nodesPerDepth = {};
        let maxDepth = 0;
        tempDescendants.forEach(d => {
            nodesPerDepth[d.depth] = (nodesPerDepth[d.depth] || 0) + 1;
            maxDepth = Math.max(maxDepth, d.depth);
        });
        
        // Calculate compact radius following Bostock's pattern
        // Use smaller label width for standard sizes, and apply compactness factor
        const labelWidth = 50; // pixels per node label (compact spacing)
        let minRadius = 200; // reduced absolute minimum for compactness
        
        for (let depth = 1; depth <= maxDepth; depth++) {
            const nodeCount = nodesPerDepth[depth] || 0;
            if (nodeCount > 0) {
                // Calculate radius and apply compactness factor to shorten child lines
                const requiredRadius = (nodeCount * labelWidth * maxDepth) / (2 * Math.PI * depth);
                minRadius = Math.max(minRadius, requiredRadius * RADIAL_COMPACTNESS);
            }
        }
        
        // Use calculated radius for compact tree
        const calculatedRadius = Math.floor(minRadius);
        
        console.log(`[Radial Tree] Nodes per depth:`, nodesPerDepth);
        console.log(`[Radial Tree] Max depth: ${maxDepth}, Total nodes: ${tempDescendants.length}`);
        console.log(`[Radial Tree] Calculated compact radius: ${calculatedRadius}px`);
        console.log(`[Radial Tree] Standard sizes - Node: ${RADIAL_NODE_SIZE}px, Text: ${RADIAL_TEXT_SIZE}px, Compactness: ${RADIAL_COMPACTNESS}`);
        
        // Set canvas size based on radius to fit whole tree on screen
        const size = Math.floor((calculatedRadius + 150) * 2); // Reduced margin for compact layout
        const radius = calculatedRadius;

        const treeContainer = d3.select('#tree');
        if (treeContainer.empty()) {
            d3.select('body').append('svg').attr('id', 'tree');
        }
        
        const svg = d3.select('#tree')
            .attr('width', '100%')
            .attr('height', '100%')
            .attr('viewBox', `0 0 ${size} ${size}`)
            .attr('preserveAspectRatio', 'xMidYMid meet');
            
        svg.selectAll('*').remove();

        // Create main group for zoom/pan transformations
        const g = svg.append('g')
            .attr('transform', `translate(${size / 2},${size / 2})`);
        
        // Set up D3 zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 10])  // Min and max zoom levels
            .on('zoom', (event) => {
                g.attr('transform', `translate(${size / 2 + event.transform.x},${size / 2 + event.transform.y}) scale(${event.transform.k})`);
            });
        
        // Apply zoom to SVG
        svg.call(zoom);
        
        // Store zoom and SVG in global scope for zoom controls
        window.zoomBehavior = zoom;
        window.svg = svg;
        
        // Reset zoom function for "Fit to Window" button
        window.resetZoom = function() {
            svg.transition().duration(750)
                .call(zoom.transform, d3.zoomIdentity);
        };

        const breadcrumbContainer = svg.append('g')
            .attr('class', 'breadcrumb-container')
            .attr('transform', 'translate(20, 20)');

        // Get spacing multiplier from global variable (controlled by slider)
        const spacingMultiplier = window.nodeSpacingMultiplier || 1.0;
        console.log('[Radial Tree] Rendering with spacing multiplier:', spacingMultiplier);
        console.log('[Radial Tree] Using Mike Bostock approach: .size([2π, radius])');
        
        // Use Mike Bostock's canonical approach from https://gist.github.com/mbostock/4063550
        // Key: .size([2 * Math.PI, radius]) ensures siblings naturally spread around full 360° arc
        const tree = d3.tree()
            .size([2 * Math.PI, radius * 0.9])  // Full circle, use 90% for inner content + label space
            .separation((a, b) => {
                // Bostock's separation formula: siblings closer, non-siblings farther
                return (a.parent === b.parent ? 1 : 2) / a.depth;
            });

        const root = d3.hierarchy(processedData);
        console.log('[Radial Tree] Tree has', root.children ? root.children.length : 0, 'children');

        // Run D3 tree layout - with .size([2π, radius]), angles are already distributed 0 to 2π
        tree(root);
        
        const descendants = root.descendants();
        console.log('[Radial Tree] Layout complete - angles naturally span 0 to 2π');
        console.log('[Radial Tree] Total nodes:', descendants.length);
        
        // LINEAGE-FIRST POSITIONING: Position lineage nodes sequentially, then fit others around them
        // Extract lineage chain in hierarchical order (root → searched account)
        const lineageChain = [];
        descendants.forEach(d => {
            if (d.data && d.data.is_lineage_path) {
                lineageChain.push(d);
            }
        });
        
        // Sort lineage by depth to get correct order (parent → child)
        lineageChain.sort((a, b) => a.depth - b.depth);
        
        console.log('[Lineage-First Layout] Found', lineageChain.length, 'lineage nodes');
        
        // Store original angles from D3 layout BEFORE we modify anything
        const originalAngles = new Map();
        descendants.forEach(d => originalAngles.set(d, d.x));
        
        if (lineageChain.length > 1) {
            // FIBONACCI SPIRAL: Use golden angle for natural, organic spacing
            // Golden angle ≈ 137.508° (2π / φ², where φ is the golden ratio)
            const goldenAngle = Math.PI * (3 - Math.sqrt(5)); // ≈ 2.399963 radians ≈ 137.508°
            
            console.log('[Lineage-First Layout] Using Fibonacci spiral with golden angle:', 
                       (goldenAngle * 180 / Math.PI).toFixed(3), '°');
            
            // Calculate angle per node, scaling down for compactness
            // But ensure the total sector never exceeds reasonable bounds
            const maxSectorSize = Math.PI; // Max 180° for lineage (leave half circle for others)
            let anglePerNode = goldenAngle * 0.05; // Start with ~6.9° per node for tight spiral
            
            // Adjust if lineage chain would exceed max sector
            let lineageSectorSize = (lineageChain.length - 1) * anglePerNode;
            if (lineageSectorSize > maxSectorSize) {
                // Scale down to fit within max sector
                anglePerNode = maxSectorSize / (lineageChain.length - 1);
                lineageSectorSize = maxSectorSize;
                console.log('[Lineage-First Layout] Adjusted angle per node to fit:', 
                           (anglePerNode * 180 / Math.PI).toFixed(1), '°');
            }
            
            // Center the spiral around 0 radians (top of circle)
            // This ensures the median lineage node sits on the vertical axis
            const lineageSectorStart = -(lineageSectorSize / 2);
            const lineageSectorEnd = +(lineageSectorSize / 2);
            
            console.log('[Lineage-First Layout] Fibonacci sector:', 
                       (lineageSectorStart * 180 / Math.PI).toFixed(1), '° to',
                       (lineageSectorEnd * 180 / Math.PI).toFixed(1), '°',
                       '(', (lineageSectorSize * 180 / Math.PI).toFixed(1), '° total)');
            
            // Compress lineage radii to keep spiral compact and inside circle
            // Find the max depth in lineage chain
            const maxLineageDepth = Math.max(...lineageChain.map(d => d.depth));
            const maxLineageRadius = radius * 0.5; // Cap lineage at 50% of circle radius
            
            console.log('[Lineage-First Layout] Compressing lineage radii to', 
                       maxLineageRadius.toFixed(1), 'px (50% of circle)');
            
            // Position lineage nodes sequentially in spiral pattern
            lineageChain.forEach((node, i) => {
                // Progress through the sector following fibonacci-inspired spacing
                node.x = lineageSectorStart + (i * anglePerNode);
                
                // Compress radial position to keep spiral compact
                // Map depth 0..maxLineageDepth to radius 0..maxLineageRadius
                const depthRatio = maxLineageDepth > 0 ? node.depth / maxLineageDepth : 0;
                node.y = depthRatio * maxLineageRadius;
                
                console.log(`  Lineage[${i}] ${node.data.stellar_account || node.data.name} →`, 
                           (node.x * 180 / Math.PI).toFixed(1), '°,',
                           'r=' + node.y.toFixed(1) + 'px');
            });
            
            // REDISTRIBUTE NON-LINEAGE PARENT GROUPS to utilize full circle space
            const nonLineageNodes = descendants.filter(d => !d.data || !d.data.is_lineage_path);
            
            // Find max depth of all nodes to determine safe radius cap
            const maxDepth = Math.max(...descendants.map(d => d.depth));
            const maxSafeRadius = radius * 0.9; // Cap all nodes at 90% of circle to stay inside
            
            // Group non-lineage nodes by their parent
            const parentGroups = new Map();
            nonLineageNodes.forEach(node => {
                const parentId = node.parent ? (node.parent.data.stellar_account || node.parent.data.name) : 'root';
                if (!parentGroups.has(parentId)) {
                    parentGroups.set(parentId, {
                        parent: node.parent,
                        children: [],
                        descendantCount: 0
                    });
                }
                const group = parentGroups.get(parentId);
                group.children.push(node);
                // Count all descendants recursively for weighting
                group.descendantCount += 1 + (node.descendants ? node.descendants().length - 1 : 0);
            });
            
            console.log('[Lineage-First Layout] Found', parentGroups.size, 'parent groups with',
                       nonLineageNodes.length, 'total non-lineage nodes');
            
            // Calculate available angular space (full circle minus lineage sector)
            const availableAngle = 2 * Math.PI - lineageSectorSize;
            const availableStart = lineageSectorEnd;
            const availableEnd = availableStart + availableAngle;
            
            // Distribute parent groups evenly across available space
            const groupsArray = Array.from(parentGroups.values());
            const totalDescendants = groupsArray.reduce((sum, g) => sum + g.descendantCount, 0);
            
            let currentAngle = availableStart;
            groupsArray.forEach((group, groupIndex) => {
                // Allocate angular space proportional to group size
                const groupWeight = totalDescendants > 0 ? group.descendantCount / totalDescendants : 1 / groupsArray.length;
                const groupAngleSpan = availableAngle * groupWeight;
                const groupCenterAngle = currentAngle + (groupAngleSpan / 2);
                
                console.log(`  Group[${groupIndex}] (${group.children.length} children,`,
                           `${group.descendantCount} descendants) → center angle:`,
                           (groupCenterAngle * 180 / Math.PI).toFixed(1), '°');
                
                // Position each child in the group relative to group center
                group.children.forEach(node => {
                    if (node.parent) {
                        // Calculate angular offset from parent in original D3 layout
                        const originalParentAngle = originalAngles.get(node.parent);
                        const originalNodeAngle = originalAngles.get(node);
                        let angularOffset = originalNodeAngle - originalParentAngle;
                        
                        // Normalize offset to [-π, π]
                        while (angularOffset > Math.PI) angularOffset -= 2 * Math.PI;
                        while (angularOffset < -Math.PI) angularOffset += 2 * Math.PI;
                        
                        // Position child relative to group center angle (preserves sibling spacing)
                        node.x = (groupCenterAngle + angularOffset) % (2 * Math.PI);
                        if (node.x < 0) node.x += 2 * Math.PI;
                    } else {
                        // Root node or orphan - use group center angle
                        node.x = groupCenterAngle;
                    }
                    
                    // Cap radius to keep nodes inside circle boundary
                    const depthRatio = maxDepth > 0 ? node.depth / maxDepth : 0;
                    node.y = Math.min(node.y, depthRatio * maxSafeRadius);
                });
                
                currentAngle += groupAngleSpan;
            });
            
            console.log('[Lineage-First Layout] Complete - lineage path is now sequential');
        } else {
            console.log('[Lineage-First Layout] Skipping - only', lineageChain.length, 'lineage node(s)');
        }
        
        // Let D3's natural layout handle spacing - .size([2π, radius]) already spreads nodes
        // around the full 360° circle, so no manual redistribution needed!

        // Debug counter for logging
        let linkCounter = 0;
        
        // Custom link generator for lineage paths that takes the shortest angular path
        // Uses manual SVG arc construction to ensure shortest path around the circle
        function buildShortestRadialLink(linkData) {
            const sourceAngle = linkData.source.x;
            const sourceRadius = linkData.source.y;
            const targetAngle = linkData.target.x;
            const targetRadius = linkData.target.y;
            
            // Calculate angular difference
            let angleDelta = targetAngle - sourceAngle;
            
            // Normalize to shortest path: wrap to [-π, π]
            while (angleDelta > Math.PI) angleDelta -= 2 * Math.PI;
            while (angleDelta < -Math.PI) angleDelta += 2 * Math.PI;
            
            // Convert polar to cartesian for source
            const sourceX = sourceRadius * Math.cos(sourceAngle - Math.PI / 2);
            const sourceY = sourceRadius * Math.sin(sourceAngle - Math.PI / 2);
            
            // For target, use the adjusted angle that takes the shortest path
            const adjustedTargetAngle = sourceAngle + angleDelta;
            const targetX = targetRadius * Math.cos(adjustedTargetAngle - Math.PI / 2);
            const targetY = targetRadius * Math.sin(adjustedTargetAngle - Math.PI / 2);
            
            // Create smooth cubic bezier curve using radial control points
            // Place control points at the midpoint radius, following the angular path
            const midRadius = (sourceRadius + targetRadius) / 2;
            const midAngle1 = sourceAngle + angleDelta * 0.33;
            const midAngle2 = sourceAngle + angleDelta * 0.67;
            
            const cp1X = midRadius * Math.cos(midAngle1 - Math.PI / 2);
            const cp1Y = midRadius * Math.sin(midAngle1 - Math.PI / 2);
            const cp2X = midRadius * Math.cos(midAngle2 - Math.PI / 2);
            const cp2Y = midRadius * Math.sin(midAngle2 - Math.PI / 2);
            
            // Return SVG path: M (move to source) C (cubic bezier to target)
            return `M${sourceX},${sourceY} C${cp1X},${cp1Y} ${cp2X},${cp2Y} ${targetX},${targetY}`;
        }
        
        const link = g.selectAll('.link')
            .data(root.links())
            .enter().append('path')
            .attr('class', d => {
                // CRITICAL: Use CSS classes for persistent styling
                let classes = ['link'];
                if (d.target.data && d.target.data.is_lineage_path) {
                    classes.push('link-lineage');  // Persistent red lineage class
                } else if (d.target.data && d.target.data.is_sibling) {
                    classes.push('link-sibling');  // Gray sibling class
                }
                return classes.join(' ');
            })
            .attr('d', d => {
                // Use shortest path for lineage links, standard radial for others
                if (d.target.data && d.target.data.is_lineage_path) {
                    return buildShortestRadialLink(d);
                } else {
                    return d3.linkRadial()
                        .angle(d => d.x)
                        .radius(d => d.y)(d);
                }
            })
            .style('stroke', d => {
                // Debug: Log link metadata for first 5 links
                if (linkCounter < 5) {
                    console.log('[Radial Link Color]', 
                        'target:', d.target.data.stellar_account || d.target.data.name,
                        'is_lineage_path:', d.target.data.is_lineage_path,
                        'is_sibling:', d.target.data.is_sibling);
                    linkCounter++;
                }
                
                // Color coding: Red for direct lineage path, Gray for siblings
                if (d.target.data && d.target.data.is_lineage_path) {
                    return '#ff3366';  // Red for direct lineage path
                } else if (d.target.data && d.target.data.is_sibling) {
                    return '#888888';  // Gray for siblings
                }
                return '#3f2c70';  // Default cyberpunk purple
            })
            .style('stroke-width', d => {
                // Thicker lines for lineage path
                return (d.target.data && d.target.data.is_lineage_path) ? '2.5px' : '1.5px';
            })
            .style('fill', 'none')
            .style('opacity', d => {
                // More prominent lineage path
                return (d.target.data && d.target.data.is_lineage_path) ? 0.9 : 0.5;
            })
            .on('mouseover', function(event, d) {
                // Add green glow ONLY to non-lineage links on hover
                if (!d.target.data || !d.target.data.is_lineage_path) {
                    d3.select(this)
                        .style('filter', 'drop-shadow(0 0 4px #00ff00)')
                        .style('stroke-width', '3px');
                }
            })
            .on('mouseout', function(event, d) {
                // Remove green glow from non-lineage links
                if (!d.target.data || !d.target.data.is_lineage_path) {
                    d3.select(this)
                        .style('filter', 'none')
                        .style('stroke-width', d.target.data && d.target.data.is_sibling ? '1.5px' : '1.5px');
                }
            });

        const node = g.selectAll('.node')
            .data(root.descendants())
            .enter().append('g')
            .attr('class', 'node')
            .attr('transform', d => {
                const angle = (d.x * 180 / Math.PI) - 90;
                return `rotate(${angle})translate(${d.y},0)`;
            });

        node.append('circle')
            .attr('r', d => {
                // Fixed standard size with slight increase for searched account
                return d.data.is_searched_account ? RADIAL_NODE_SIZE + 1.5 : RADIAL_NODE_SIZE;
            })
            .attr('data-node-type', d => d.data.node_type)
            .style('fill', d => {
                // Check if node should be muted (filtered)
                if (window.shouldMuteNode && window.shouldMuteNode(d.data)) {
                    return '#1a1a2e';  // Dark background color (muted)
                }
                return '#3f2c70';  // Normal cyberpunk purple
            })
            .style('stroke', d => {
                // Check if node should be muted (filtered)
                if (window.shouldMuteNode && window.shouldMuteNode(d.data)) {
                    return '#2a2a3e';  // Slightly lighter dark (muted)
                }
                // Cyan glow for searched account
                if (d.data.is_searched_account) {
                    return '#00ffff';  // Cyan for searched account
                }
                // Yellow for assets, green for issuers
                return d.data.node_type === 'ASSET' ? '#fcec04' : '#00FF9C';
            })
            .style('stroke-width', d => d.data.is_searched_account ? '4px' : '2px')
            .style('opacity', d => {
                // Reduce opacity for muted nodes
                if (window.shouldMuteNode && window.shouldMuteNode(d.data)) {
                    return 0.2;  // Very dim for filtered nodes
                }
                return 1;  // Normal visibility
            })
            .style('filter', d => d.data.is_searched_account ? 'drop-shadow(0 0 8px #00ffff)' : 'none')
            .on('mouseover', function(event, d) { showTooltip(event, d); })
            .on('mouseout', function(event, d) { hideTooltip(); });

        node.append('text')
            .attr('dy', '.31em')
            .attr('x', d => d.x < Math.PI ? 12 : -12)
            .attr('text-anchor', d => d.x < Math.PI ? 'start' : 'end')
            .attr('transform', d => d.x >= Math.PI ? 'rotate(180)' : null)
            .text(d => {
                // For ISSUER nodes (stellar_account), show last 7 characters
                if (d.data.stellar_account && d.data.node_type === 'ISSUER') {
                    return d.data.stellar_account.slice(-7);
                }
                // For ASSET nodes, show the asset code
                return d.data.asset_code || d.data.name || 'Unnamed';
            })
            .style('fill', 'white')
            .style('font-size', RADIAL_TEXT_SIZE + 'px')
            .style('font-weight', '500')
            .style('text-shadow', '1px 1px 2px rgba(0,0,0,0.8)')
            .style('opacity', d => {
                // Reduce opacity for muted nodes
                if (window.shouldMuteNode && window.shouldMuteNode(d.data)) {
                    return 0.15;  // Very dim text for filtered nodes
                }
                return 1;  // Normal visibility
            });

        let tooltip = d3.select('body').select('.tooltip');
        if (tooltip.empty()) {
            tooltip = d3.select('body').append('div')
                .attr('class', 'tooltip')
                .style('opacity', 0)
                .style('position', 'absolute')
                .style('color', 'black')
                .style('padding', '10px')
                .style('border-radius', '6px')
                .style('box-shadow', '3px 3px 10px rgba(0, 0, 0, 0.25)')
                .style('font', '12px sans-serif')
                .style('width', '250px')
                .style('word-wrap', 'break-word')
                .style('pointer-events', 'none')
                .style('z-index', '1000');
        }

        function getPathToRoot(node) {
            const path = [];
            let current = node;
            while (current) {
                path.unshift(current);
                current = current.parent;
            }
            return path;
        }

        function showTooltip(event, d) {
            const nodeColor = d.data.node_type === 'ASSET' ? '#fcec04' : '#3f2c70';
            const backgroundColor = d.data.node_type === 'ASSET' ? 'rgba(252, 236, 4, 0.9)' : 'rgba(63, 44, 112, 0.9)';
            const textColor = d.data.node_type === 'ASSET' ? 'black' : 'white';
            
            const pathToRoot = getPathToRoot(d);
            const pathLinks = new Set();
            for (let i = 1; i < pathToRoot.length; i++) {
                pathLinks.add(`${pathToRoot[i-1].data.stellar_account || pathToRoot[i-1].data.asset_code || pathToRoot[i-1].data.name || 'root'}_${pathToRoot[i].data.stellar_account || pathToRoot[i].data.asset_code || pathToRoot[i].data.name}`);
            }
            
            link.style('stroke', linkData => {
                const linkId = `${linkData.source.data.stellar_account || linkData.source.data.asset_code || linkData.source.data.name || 'root'}_${linkData.target.data.stellar_account || linkData.target.data.asset_code || linkData.target.data.name}`;
                return pathLinks.has(linkId) ? '#ff0000' : '#3f2c70';
            })
            .style('stroke-width', linkData => {
                const linkId = `${linkData.source.data.stellar_account || linkData.source.data.asset_code || linkData.source.data.name || 'root'}_${linkData.target.data.stellar_account || linkData.target.data.asset_code || linkData.target.data.name}`;
                return pathLinks.has(linkId) ? '3px' : '1.5px';
            })
            .style('opacity', linkData => {
                const linkId = `${linkData.source.data.stellar_account || linkData.source.data.asset_code || linkData.source.data.name || 'root'}_${linkData.target.data.stellar_account || linkData.target.data.asset_code || linkData.target.data.name}`;
                return pathLinks.has(linkId) ? 1 : 0.3;
            });

            breadcrumbContainer.selectAll('*').remove();
            
            let xOffset = 0;
            pathToRoot.forEach((node, i) => {
                const breadcrumbColor = node.data.node_type === 'ASSET' ? '#fcec04' : '#3f2c70';
                // Truncate ISSUER stellar_account to last 7 characters for breadcrumb
                let breadcrumbText;
                if (node.data.stellar_account && node.data.node_type === 'ISSUER') {
                    breadcrumbText = node.data.stellar_account.slice(-7);
                } else {
                    breadcrumbText = node.data.stellar_account || node.data.asset_code || node.data.name || 'Root';
                }
                const textWidth = breadcrumbText.length * 7;
                
                breadcrumbContainer.append('rect')
                    .attr('x', xOffset)
                    .attr('y', 0)
                    .attr('width', textWidth + 20)
                    .attr('height', 25)
                    .attr('fill', breadcrumbColor)
                    .attr('rx', 4);
                
                breadcrumbContainer.append('text')
                    .attr('x', xOffset + 10)
                    .attr('y', 17)
                    .text(breadcrumbText)
                    .style('fill', node.data.node_type === 'ASSET' ? 'black' : 'white')
                    .style('font-size', '12px')
                    .style('font-weight', 'bold');
                
                xOffset += textWidth + 25;
                
                if (i < pathToRoot.length - 1) {
                    breadcrumbContainer.append('text')
                        .attr('x', xOffset)
                        .attr('y', 17)
                        .text('>')
                        .style('fill', 'white')
                        .style('font-size', '14px')
                        .style('font-weight', 'bold');
                    xOffset += 20;
                }
            });
            
            let tooltipHTML = '<b>Name:</b> ' + (d.data.stellar_account || d.data.asset_code || d.data.name || 'Unnamed') + '<br>';
            if (d.data.node_type === 'ASSET') {
                tooltipHTML += '<b>Issuer:</b> ' + (d.data.asset_issuer || 'N/A') + '<br>';
                tooltipHTML += '<b>Asset Type:</b> ' + (d.data.asset_type || 'N/A') + '<br>';
                tooltipHTML += '<b>Balance:</b> ' + (parseFloat(d.data.balance || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })) + '<br>';
            } else {
                tooltipHTML += '<b>Created:</b> ' + (d.data.created || 'N/A') + '<br>';
                tooltipHTML += '<b>Home Domain:</b> ' + (d.data.home_domain || 'N/A') + '<br>';
                tooltipHTML += '<b>XLM Balance:</b> ' + (parseFloat(d.data.xlm_balance || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })) + '<br>';
                tooltipHTML += '<b>Creator:</b> ' + (d.data.creator_account || 'N/A') + '<br>';
            }
            tooltip.html(tooltipHTML)
                .style('background', backgroundColor)
                .style('color', textColor)
                .style('opacity', 1);
            
            // Smart positioning to prevent tooltip from going off-screen
            const tooltipNode = tooltip.node();
            const tooltipRect = tooltipNode.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;
            
            // Use clientX/Y for viewport-relative positioning, then convert to page coordinates
            let left = event.clientX + 10;
            let top = event.clientY - 28;
            
            // Check right edge - if tooltip goes off-screen, show on left side of cursor
            if (left + tooltipRect.width > viewportWidth) {
                left = event.clientX - tooltipRect.width - 10;
            }
            
            // Check left edge - ensure tooltip doesn't go off left side
            if (left < 0) {
                left = 10;
            }
            
            // Check bottom edge - if tooltip goes off-screen, show above cursor
            if (top + tooltipRect.height > viewportHeight) {
                top = event.clientY - tooltipRect.height - 10;
            }
            
            // Check top edge - ensure tooltip doesn't go off top
            if (top < 0) {
                top = event.clientY + 20;
            }
            
            // Convert to page coordinates by adding scroll offsets
            tooltip.style('left', (left + window.scrollX) + 'px')
                .style('top', (top + window.scrollY) + 'px');
        }

        function hideTooltip() {
            tooltip.style('opacity', 0);
            
            // CRITICAL FIX: Don't reset ALL links - restore based on their type
            link.each(function(d) {
                const linkElement = d3.select(this);
                if (d.target.data && d.target.data.is_lineage_path) {
                    // Restore red lineage links
                    linkElement
                        .style('stroke', '#ff3366')
                        .style('stroke-width', '2.5px')
                        .style('opacity', 0.9)
                        .style('filter', 'none');  // Remove any hover effects
                } else if (d.target.data && d.target.data.is_sibling) {
                    // Restore gray sibling links
                    linkElement
                        .style('stroke', '#888888')
                        .style('stroke-width', '1.5px')
                        .style('opacity', 0.5)
                        .style('filter', 'none');
                } else {
                    // Restore default purple links
                    linkElement
                        .style('stroke', '#3f2c70')
                        .style('stroke-width', '1.5px')
                        .style('opacity', 0.6)
                        .style('filter', 'none');
                }
            });
            
            breadcrumbContainer.selectAll('*').remove();
        }

        console.log('Radial tree rendered successfully');
        
    } catch (error) {
        console.error('Error rendering radial tree:', error);
        
        const svg = d3.select('#tree');
        if (!svg.empty()) {
            svg.selectAll('*').remove();
            svg.append('text')
                .attr('x', 400)
                .attr('y', 400)
                .attr('text-anchor', 'middle')
                .style('font-size', '16px')
                .style('fill', '#666')
                .text('Tree visualization unavailable');
        }
    }
}

// Global function to render left-to-right tidy tree with data
function renderTidyTree(jsonData) {
    try {
        // Store data globally so slider can re-render
        window.currentTreeData = jsonData;
        
        const existingSvg = document.querySelector('#tree');
        if (existingSvg) {
            existingSvg.innerHTML = '';
        }

        let processedData;
        if (jsonData && typeof jsonData === 'object') {
            if (jsonData.name || jsonData.children || jsonData.stellar_account) {
                processedData = jsonData;
            } else {
                processedData = {
                    name: jsonData.stellar_account || 'Root Node',
                    node_type: jsonData.node_type || 'ACCOUNT',
                    created: jsonData.created || new Date().toISOString(),
                    children: jsonData.children || []
                };
            }
        } else {
            processedData = {
                name: 'Sample Root',
                node_type: 'ACCOUNT',
                created: '2015-09-30 13:15:54',
                children: []
            };
        }

        console.log('Processing tidy tree data:', processedData);

        const container = document.querySelector('.visualization-container') || document.body;
        const containerRect = container.getBoundingClientRect();
        const width = containerRect.width || window.innerWidth;
        const height = containerRect.height || window.innerHeight;

        const margin = {top: 20, right: 250, bottom: 20, left: 60};  // Increased right margin to prevent text overflow
        const innerWidth = width - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;
        
        // Use 70% of width to leave room for text labels
        const treeWidth = innerWidth * 0.7;

        const svg = d3.select('#tree')
            .attr('width', '100%')
            .attr('height', '100%')
            .attr('viewBox', `0 0 ${width} ${height}`)
            .attr('preserveAspectRatio', 'xMidYMid meet');
            
        svg.selectAll('*').remove();

        // Create main group for zoom/pan transformations
        const g = svg.append('g')
            .attr('transform', `translate(${margin.left},${margin.top})`);
        
        // Set up D3 zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 10])  // Min and max zoom levels
            .on('zoom', (event) => {
                g.attr('transform', `translate(${margin.left + event.transform.x},${margin.top + event.transform.y}) scale(${event.transform.k})`);
            });
        
        // Apply zoom to SVG
        svg.call(zoom);
        
        // Store zoom and SVG in global scope for zoom controls
        window.zoomBehavior = zoom;
        window.svg = svg;
        
        // Reset zoom function for "Fit to Window" button
        window.resetZoom = function() {
            svg.transition().duration(750)
                .call(zoom.transform, d3.zoomIdentity);
        };

        const breadcrumbContainer = svg.append('g')
            .attr('class', 'breadcrumb-container')
            .attr('transform', 'translate(20, 20)');

        const root = d3.hierarchy(processedData);
        console.log('Tidy tree has', root.children ? root.children.length : 0, 'children');
        console.log('Tree depth:', root.height);

        // Get spacing multiplier from global variable (controlled by slider)
        const spacingMultiplier = window.nodeSpacingMultiplier || 1.0;
        console.log('Tidy tree rendering with spacing multiplier:', spacingMultiplier);
        
        // Use nodeSize instead of size to let tree expand naturally based on separation
        const nodeHeight = 25 * spacingMultiplier;  // Base height per node, scaled by multiplier
        const tree = d3.tree()
            .nodeSize([nodeHeight, 100])  // [height, width] per node - height controls vertical spacing
            .separation((a, b) => {
                // Additional separation multiplier for siblings vs non-siblings
                return a.parent === b.parent ? 1 : 1.2;
            });

        tree(root);
        
        // Get child spacing factors from global variables (configurable via UI)
        const minChildSpacing = window.minChildSpacing || 0.6;
        const maxChildSpacing = window.maxChildSpacing || 1.5;
        
        // Calculate dynamic horizontal positions based on child count
        // More children = longer lines (spread further right), fewer children = shorter lines
        const maxDepth = root.height || 1;
        const baseSpacing = treeWidth / maxDepth;
        
        root.descendants().forEach(d => {
            if (d.parent) {
                const childCount = d.parent.children ? d.parent.children.length : 1;
                // Scale factor based on child count with configurable min/max
                const scaleFactor = Math.min(maxChildSpacing, Math.max(minChildSpacing, 0.5 + (childCount / 20)));
                d.y = d.parent.y + (baseSpacing * scaleFactor);
            } else {
                d.y = 0;  // Root at origin
            }
        });

        // Center the tree vertically by finding min/max coordinates
        const descendants = root.descendants();
        const minX = d3.min(descendants, d => d.x);
        const maxX = d3.max(descendants, d => d.x);
        const treeHeight = maxX - minX;
        
        // Center vertically, or align to top if tree is larger than viewport
        const yOffset = treeHeight < innerHeight ? (innerHeight - treeHeight) / 2 - minX : -minX + 20;

        const link = g.selectAll('.link')
            .data(root.links())
            .enter().append('path')
            .attr('class', 'link')
            .attr('d', d3.linkHorizontal()
                .x(d => d.y)
                .y(d => d.x + yOffset))
            .style('stroke', d => {
                // Color coding: Red for direct lineage path, Gray for siblings
                if (d.target.data && d.target.data.is_lineage_path) {
                    return '#ff3366';  // Red for direct lineage path
                } else if (d.target.data && d.target.data.is_sibling) {
                    return '#888888';  // Gray for siblings
                }
                return '#3f2c70';  // Default cyberpunk purple
            })
            .style('stroke-width', d => {
                // Thicker lines for lineage path
                return (d.target.data && d.target.data.is_lineage_path) ? '2.5px' : '1.5px';
            })
            .style('fill', 'none')
            .style('opacity', d => {
                // More prominent lineage path
                return (d.target.data && d.target.data.is_lineage_path) ? 0.9 : 0.5;
            });

        const node = g.selectAll('.node')
            .data(descendants)
            .enter().append('g')
            .attr('class', 'node')
            .attr('transform', d => `translate(${d.y},${d.x + yOffset})`);

        node.append('circle')
            .attr('r', d => {
                // Fixed standard size with slight increase for searched account
                return d.data.is_searched_account ? RADIAL_NODE_SIZE + 1.5 : RADIAL_NODE_SIZE;
            })
            .attr('data-node-type', d => d.data.node_type)
            .style('fill', d => {
                // Check if node should be muted (filtered)
                if (window.shouldMuteNode && window.shouldMuteNode(d.data)) {
                    return '#1a1a2e';  // Dark background color (muted)
                }
                return '#3f2c70';  // Normal cyberpunk purple
            })
            .style('stroke', d => {
                // Check if node should be muted (filtered)
                if (window.shouldMuteNode && window.shouldMuteNode(d.data)) {
                    return '#2a2a3e';  // Slightly lighter dark (muted)
                }
                // Cyan glow for searched account
                if (d.data.is_searched_account) {
                    return '#00ffff';  // Cyan for searched account
                }
                // Yellow for assets, green for issuers
                return d.data.node_type === 'ASSET' ? '#fcec04' : '#00FF9C';
            })
            .style('stroke-width', d => d.data.is_searched_account ? '4px' : '2.5px')
            .style('opacity', d => {
                // Reduce opacity for muted nodes
                if (window.shouldMuteNode && window.shouldMuteNode(d.data)) {
                    return 0.2;  // Very dim for filtered nodes
                }
                return 1;  // Normal visibility
            })
            .style('filter', d => d.data.is_searched_account ? 'drop-shadow(0 0 10px #00ffff)' : 'none')
            .on('mouseover', function(event, d) { showTidyTooltip(event, d); })
            .on('mouseout', function(event, d) { hideTidyTooltip(); });

        node.append('text')
            .attr('dy', '0.31em')
            .attr('x', d => d.children ? -14 : 14)  // Increased offset to prevent overlap with larger circles
            .attr('text-anchor', d => d.children ? 'end' : 'start')
            .text(d => {
                if (d.data.stellar_account && d.data.node_type === 'ISSUER') {
                    return d.data.stellar_account.slice(-7);
                }
                return d.data.asset_code || d.data.name || 'Unnamed';
            })
            .style('fill', 'white')
            .style('font-size', RADIAL_TEXT_SIZE + 'px')
            .style('font-weight', '400')  // Reduced from 600 for better readability (normal weight)
            .style('text-shadow', '1px 1px 3px rgba(0,0,0,0.9)')  // Adjusted shadow for clarity
            .style('letter-spacing', '0.5px')  // Slightly increased letter spacing for clarity
            .style('opacity', d => {
                // Reduce opacity for muted nodes
                if (window.shouldMuteNode && window.shouldMuteNode(d.data)) {
                    return 0.15;  // Very dim text for filtered nodes
                }
                return 1;  // Normal visibility
            });

        let tooltip = d3.select('body').select('.tooltip');
        if (tooltip.empty()) {
            tooltip = d3.select('body').append('div')
                .attr('class', 'tooltip')
                .style('opacity', 0)
                .style('position', 'absolute')
                .style('color', 'black')
                .style('padding', '10px')
                .style('border-radius', '6px')
                .style('box-shadow', '3px 3px 10px rgba(0, 0, 0, 0.25)')
                .style('font', '12px sans-serif')
                .style('width', '250px')
                .style('word-wrap', 'break-word')
                .style('pointer-events', 'none')
                .style('z-index', '1000');
        }

        function getPathToRoot(node) {
            const path = [];
            let current = node;
            while (current) {
                path.unshift(current);
                current = current.parent;
            }
            return path;
        }

        function showTidyTooltip(event, d) {
            const nodeColor = d.data.node_type === 'ASSET' ? '#fcec04' : '#3f2c70';
            const backgroundColor = d.data.node_type === 'ASSET' ? 'rgba(252, 236, 4, 0.9)' : 'rgba(63, 44, 112, 0.9)';
            const textColor = d.data.node_type === 'ASSET' ? 'black' : 'white';
            
            const pathToRoot = getPathToRoot(d);
            const pathLinks = new Set();
            for (let i = 1; i < pathToRoot.length; i++) {
                pathLinks.add(`${pathToRoot[i-1].data.stellar_account || pathToRoot[i-1].data.asset_code || pathToRoot[i-1].data.name || 'root'}_${pathToRoot[i].data.stellar_account || pathToRoot[i].data.asset_code || pathToRoot[i].data.name}`);
            }
            
            link.style('stroke', linkData => {
                const linkId = `${linkData.source.data.stellar_account || linkData.source.data.asset_code || linkData.source.data.name || 'root'}_${linkData.target.data.stellar_account || linkData.target.data.asset_code || linkData.target.data.name}`;
                return pathLinks.has(linkId) ? '#ff0000' : '#3f2c70';
            })
            .style('stroke-width', linkData => {
                const linkId = `${linkData.source.data.stellar_account || linkData.source.data.asset_code || linkData.source.data.name || 'root'}_${linkData.target.data.stellar_account || linkData.target.data.asset_code || linkData.target.data.name}`;
                return pathLinks.has(linkId) ? '3px' : '1.5px';
            })
            .style('opacity', linkData => {
                const linkId = `${linkData.source.data.stellar_account || linkData.source.data.asset_code || linkData.source.data.name || 'root'}_${linkData.target.data.stellar_account || linkData.target.data.asset_code || linkData.target.data.name}`;
                return pathLinks.has(linkId) ? 1 : 0.3;
            });

            breadcrumbContainer.selectAll('*').remove();
            
            let xOffset = 0;
            pathToRoot.forEach((node, i) => {
                const breadcrumbColor = node.data.node_type === 'ASSET' ? '#fcec04' : '#3f2c70';
                let breadcrumbText;
                if (node.data.stellar_account && node.data.node_type === 'ISSUER') {
                    breadcrumbText = node.data.stellar_account.slice(-7);
                } else {
                    breadcrumbText = node.data.stellar_account || node.data.asset_code || node.data.name || 'Root';
                }
                const textWidth = breadcrumbText.length * 7;
                
                breadcrumbContainer.append('rect')
                    .attr('x', xOffset)
                    .attr('y', 0)
                    .attr('width', textWidth + 20)
                    .attr('height', 25)
                    .attr('fill', breadcrumbColor)
                    .attr('rx', 4);
                
                breadcrumbContainer.append('text')
                    .attr('x', xOffset + 10)
                    .attr('y', 17)
                    .text(breadcrumbText)
                    .style('fill', node.data.node_type === 'ASSET' ? 'black' : 'white')
                    .style('font-size', '12px')
                    .style('font-weight', 'bold');
                
                xOffset += textWidth + 25;
                
                if (i < pathToRoot.length - 1) {
                    breadcrumbContainer.append('text')
                        .attr('x', xOffset)
                        .attr('y', 17)
                        .text('>')
                        .style('fill', 'white')
                        .style('font-size', '14px')
                        .style('font-weight', 'bold');
                    xOffset += 20;
                }
            });
            
            let tooltipHTML = '<b>Name:</b> ' + (d.data.stellar_account || d.data.asset_code || d.data.name || 'Unnamed') + '<br>';
            if (d.data.node_type === 'ASSET') {
                tooltipHTML += '<b>Issuer:</b> ' + (d.data.asset_issuer || 'N/A') + '<br>';
                tooltipHTML += '<b>Asset Type:</b> ' + (d.data.asset_type || 'N/A') + '<br>';
                tooltipHTML += '<b>Balance:</b> ' + (parseFloat(d.data.balance || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })) + '<br>';
            } else {
                tooltipHTML += '<b>Created:</b> ' + (d.data.created || 'N/A') + '<br>';
                tooltipHTML += '<b>Home Domain:</b> ' + (d.data.home_domain || 'N/A') + '<br>';
                tooltipHTML += '<b>XLM Balance:</b> ' + (parseFloat(d.data.xlm_balance || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })) + '<br>';
                tooltipHTML += '<b>Creator:</b> ' + (d.data.creator_account || 'N/A') + '<br>';
            }
            tooltip.html(tooltipHTML)
                .style('background', backgroundColor)
                .style('color', textColor)
                .style('opacity', 1);
            
            // Smart positioning to prevent tooltip from going off-screen
            const tooltipNode = tooltip.node();
            const tooltipRect = tooltipNode.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;
            
            // Use clientX/Y for viewport-relative positioning, then convert to page coordinates
            let left = event.clientX + 10;
            let top = event.clientY - 28;
            
            // Check right edge - if tooltip goes off-screen, show on left side of cursor
            if (left + tooltipRect.width > viewportWidth) {
                left = event.clientX - tooltipRect.width - 10;
            }
            
            // Check left edge - ensure tooltip doesn't go off left side
            if (left < 0) {
                left = 10;
            }
            
            // Check bottom edge - if tooltip goes off-screen, show above cursor
            if (top + tooltipRect.height > viewportHeight) {
                top = event.clientY - tooltipRect.height - 10;
            }
            
            // Check top edge - ensure tooltip doesn't go off top
            if (top < 0) {
                top = event.clientY + 20;
            }
            
            // Convert to page coordinates by adding scroll offsets
            tooltip.style('left', (left + window.scrollX) + 'px')
                .style('top', (top + window.scrollY) + 'px');
        }

        function hideTidyTooltip() {
            tooltip.style('opacity', 0);
            
            link.style('stroke', '#3f2c70')
                .style('stroke-width', '1.5px')
                .style('opacity', 0.6);
            
            breadcrumbContainer.selectAll('*').remove();
        }

        console.log('Tidy tree rendered successfully');
        
    } catch (error) {
        console.error('Error rendering tidy tree:', error);
        
        const svg = d3.select('#tree');
        if (!svg.empty()) {
            svg.selectAll('*').remove();
            svg.append('text')
                .attr('x', 400)
                .attr('y', 400)
                .attr('text-anchor', 'middle')
                .style('font-size', '16px')
                .style('fill', '#666')
                .text('Tree visualization unavailable');
        }
    }
}