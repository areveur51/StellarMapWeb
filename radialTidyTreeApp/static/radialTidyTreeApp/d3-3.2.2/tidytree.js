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
            .attr("r", d => 10.5 / (d.depth + 1))
            .attr("fill", d => d._children ? "#555" : "#999")
            .attr("class", d => "depth_" + d.depth);


        nodeEnter.append("text")
            .attr("dy", "0.31em")
            .attr("x", d => d._children ? -6 : 6)
            .attr("text-anchor", d => d._children ? "end" : "start")
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

        // Pre-analyze tree to calculate optimal radius based on node density
        const tempRoot = d3.hierarchy(processedData);
        const descendants = tempRoot.descendants();
        
        // Count nodes at each depth level
        const nodesPerDepth = {};
        let maxDepth = 0;
        descendants.forEach(d => {
            nodesPerDepth[d.depth] = (nodesPerDepth[d.depth] || 0) + 1;
            maxDepth = Math.max(maxDepth, d.depth);
        });
        
        // Calculate minimum radius needed for the densest level
        // For 56-char Stellar addresses, we need ~100px circumferential space per label
        // Circumference at depth d: 2πr, where r = (d / maxDepth) * radius
        // Required: nodesAtDepth * 100px ≤ 2π * (d / maxDepth) * radius
        let minRadius = 300; // Minimum baseline radius
        
        for (let depth = 1; depth <= maxDepth; depth++) {
            const nodeCount = nodesPerDepth[depth] || 0;
            if (nodeCount > 0) {
                // Calculate radius needed for this depth level
                // labelWidth * nodeCount = circumference at this depth
                // 100 * nodeCount = 2π * (depth / maxDepth) * radius
                const labelWidth = 100; // px per label
                const requiredRadius = (labelWidth * nodeCount * maxDepth) / (2 * Math.PI * depth);
                minRadius = Math.max(minRadius, requiredRadius);
            }
        }
        
        console.log(`[Radial Tree] Node density analysis:`, nodesPerDepth);
        console.log(`[Radial Tree] Max depth: ${maxDepth}, Total nodes: ${descendants.length}`);
        console.log(`[Radial Tree] Calculated minimum radius: ${minRadius.toFixed(0)}px`);
        
        // Use calculated radius, but cap at reasonable limits
        const calculatedRadius = Math.min(minRadius * 1.1, 2000); // 10% padding, max 2000px
        
        // Set canvas size based on radius
        const size = (calculatedRadius + 150) * 2; // Add margin for labels
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
        
        // Use Mike Bostock's proven approach from https://gist.github.com/mbostock/4063550
        // Key: .size([2 * Math.PI, radius]) ensures siblings naturally spread around full 360° arc
        const tree = d3.tree()
            .size([2 * Math.PI, radius * 0.9])  // Full circle, 90% of radius for inner content
            .separation((a, b) => {
                // Mike Bostock's separation formula adapted for our data
                // Siblings (same parent) get smaller separation, non-siblings get more
                return (a.parent === b.parent ? 1 : 2) / (a.depth + 1);
            });

        const root = d3.hierarchy(processedData);
        console.log('[Radial Tree] Tree has', root.children ? root.children.length : 0, 'children');

        // Run D3 tree layout - with .size([2π, radius]), angles are already distributed 0 to 2π
        tree(root);
        
        const descendants = root.descendants();
        console.log('[Radial Tree] Layout complete - angles naturally span 0 to 2π');
        console.log('[Radial Tree] Total nodes:', descendants.length);
        
        // Let D3's natural layout handle spacing - .size([2π, radius]) already spreads nodes
        // around the full 360° circle, so no manual redistribution needed!

        // Debug counter for logging
        let linkCounter = 0;
        
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
            .attr('d', d3.linkRadial()
                .angle(d => d.x)
                .radius(d => d.y))
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
            .attr('r', d => d.data.is_searched_account ? 7 : 5)  // Larger for searched account
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
            .style('font-size', '13px')
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
            .attr('r', d => d.data.is_searched_account ? 8 : 6)  // Larger for searched account
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
            .style('font-size', '13px')  // Reduced from 14px for less thickness
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