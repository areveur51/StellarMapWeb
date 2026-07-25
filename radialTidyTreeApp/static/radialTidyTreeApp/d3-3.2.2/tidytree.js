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

        // Pre-analyze tree: adapt radius so the densest sibling ring fills a full circle
        const tempRoot = d3.hierarchy(processedData);
        const tempDescendants = tempRoot.descendants();
        const nodesPerDepth = {};
        let maxDepth = 0;
        let maxSiblingsAtDepth = 1;
        tempDescendants.forEach(d => {
            nodesPerDepth[d.depth] = (nodesPerDepth[d.depth] || 0) + 1;
            maxDepth = Math.max(maxDepth, d.depth);
            if (d.depth > 0) {
                maxSiblingsAtDepth = Math.max(maxSiblingsAtDepth, nodesPerDepth[d.depth]);
            }
        });
        // Also consider widest sibling group under a single parent
        tempRoot.each(d => {
            if (d.children && d.children.length > maxSiblingsAtDepth) {
                maxSiblingsAtDepth = d.children.length;
            }
        });

        // Arc spacing: node diameter + gap so circles do not sit on top of each other
        const spacingMultiplier = window.nodeSpacingMultiplier || 1.0;
        const nodeHitR = RADIAL_NODE_SIZE + 1.5; // matches searched-account max circle
        const minNodeGapPx = 8; // clear air between circle edges
        const minChordPx = Math.max(
            nodeHitR * 2 + minNodeGapPx,
            28,
            34 * spacingMultiplier
        );
        // circumference ≈ 2π r  =>  r >= (siblings * minChord) / 2π
        const radiusFromSiblings = (maxSiblingsAtDepth * minChordPx) / (2 * Math.PI);
        // Depth rings need at least one full node diameter + gap between levels
        const minRadialStep = nodeHitR * 2 + minNodeGapPx + 12;
        const radiusFromDepth = Math.max(1, maxDepth) * Math.max(minRadialStep, maxSiblingsAtDepth < 20 ? 90 : 70);
        let calculatedRadius = Math.max(200, radiusFromSiblings, radiusFromDepth * RADIAL_COMPACTNESS);
        // Soft cap for small viewports (still allow zoom for dense trees)
        const hostEl = document.getElementById('radial-tree-container');
        const vw = Math.min(
            (typeof window !== 'undefined' && window.innerWidth) || 800,
            (hostEl && hostEl.clientWidth) || 800
        );
        const vh = Math.min(
            (typeof window !== 'undefined' && window.innerHeight) || 800,
            (hostEl && hostEl.clientHeight) || 640
        );
        const viewportCap = Math.max(180, Math.min(vw, vh) * 0.48);
        if (calculatedRadius > viewportCap * 2.2) {
            calculatedRadius = viewportCap * 2.2;
        }
        calculatedRadius = Math.floor(calculatedRadius);
        let size = Math.floor((calculatedRadius + 100) * 2);
        let radius = calculatedRadius;

        ensureTreeChrome();

        const treeContainer = d3.select('#tree');
        if (treeContainer.empty()) {
            d3.select('body').append('svg').attr('id', 'tree');
        }

        const svg = d3.select('#tree')
            .attr('width', '100%')
            .attr('height', '100%')
            .attr('viewBox', `0 0 ${size} ${size}`)
            .attr('preserveAspectRatio', 'xMidYMid meet')
            .style('touch-action', 'none'); // pan/zoom without page scroll fighting

        svg.selectAll('*').remove();
        // Remove legacy floating tooltip / SVG breadcrumb artifacts (looked like pinned nodes)
        d3.selectAll('body > .tooltip').remove();
        d3.selectAll('#radial-tree-container .breadcrumb-container').remove();
        clearTreeSelectionUI();

        const g = svg.append('g')
            .attr('class', 'sm-tree-zoom-layer')
            .attr('transform', `translate(${size / 2},${size / 2})`);

        const zoom = d3.zoom()
            .scaleExtent([0.12, 8])
            .filter((event) => {
                // Allow node clicks; block only primary-button pan from starting on nodes
                if (event.type === 'wheel') return true;
                if (event.target && event.target.closest && event.target.closest('.node')) {
                    return event.type === 'wheel';
                }
                return !event.ctrlKey || event.type === 'wheel';
            })
            .on('zoom', (event) => {
                g.attr(
                    'transform',
                    `translate(${size / 2 + event.transform.x},${size / 2 + event.transform.y}) scale(${event.transform.k})`
                );
            });
        svg.call(zoom);
        window.zoomBehavior = zoom;
        window.svg = svg;
        window.resetZoom = function () {
            svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
        };

        // Full-circle layout: angles span [0, 2π] so siblings complete a radial ring
        // (no lineage-sector clamp — that left half the circle empty with few siblings)
        const tree = d3.tree()
            .size([2 * Math.PI, radius * 0.88])
            .separation((a, b) => {
                // Equal weight among siblings so a ring fills evenly;
                // slight extra gap between different parents
                if (a.parent === b.parent) {
                    return 1;
                }
                return 1.35;
            });

        const root = d3.hierarchy(processedData);
        tree(root);
        const descendants = root.descendants();

        // Normalize angles into [0, 2π] after layout (stable for polar projection)
        let minX = Infinity;
        let maxX = -Infinity;
        descendants.forEach(d => {
            if (d.x < minX) minX = d.x;
            if (d.x > maxX) maxX = d.x;
        });
        const spanX = maxX - minX || 1;
        if (Math.abs(spanX - 2 * Math.PI) > 0.05 || minX < -0.01 || maxX > 2 * Math.PI + 0.01) {
            // Normalize angles to [0, 2π] so the ring is complete
            descendants.forEach(d => {
                d.x = ((d.x - minX) / spanX) * 2 * Math.PI;
            });
        }

        // Soft radial scale: few nodes stretch outward; dense trees stay compact
        const totalNodeCount = descendants.length;
        let radialScale = 1;
        if (totalNodeCount < 30) radialScale = 1.05;
        else if (totalNodeCount > 200) radialScale = 0.92;
        if (radialScale !== 1) {
            descendants.forEach(d => {
                d.y = d.y * radialScale;
            });
        }

        // Post-layout: enforce non-overlapping node circles (angular + radial)
        resolveRadialNodeOverlaps(descendants, {
            nodeRadius: nodeHitR,
            minGap: minNodeGapPx,
            minRadialStep: minRadialStep
        });

        // Expand canvas if outer ring grew past original radius budget
        let maxY = 0;
        descendants.forEach(d => { if (d.y > maxY) maxY = d.y; });
        if (maxY > radius * 0.92) {
            radius = Math.ceil(maxY / 0.88);
            size = Math.floor((radius + 100) * 2);
            svg.attr('viewBox', `0 0 ${size} ${size}`);
            g.attr('transform', `translate(${size / 2},${size / 2})`);
        }

        const debugRadial = !!(typeof window !== 'undefined' && window.SM_DEBUG_RADIAL);
        
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
            })
            .style('cursor', 'pointer');

        function circleFill(d) {
            if (window.shouldMuteNode && window.shouldMuteNode(d.data)) return '#1a1a2e';
            return '#3f2c70';
        }
        function circleStroke(d) {
            if (window.shouldMuteNode && window.shouldMuteNode(d.data)) return '#2a2a3e';
            if (d.data.is_searched_account) return '#00ffff';
            return d.data.node_type === 'ASSET' ? '#fcec04' : '#00FF9C';
        }

        node.append('circle')
            .attr('r', d => {
                return d.data.is_searched_account ? RADIAL_NODE_SIZE + 1.5 : RADIAL_NODE_SIZE;
            })
            .attr('data-node-type', d => d.data.node_type)
            .style('fill', circleFill)
            .style('stroke', circleStroke)
            .style('stroke-width', d => d.data.is_searched_account ? '4px' : '2px')
            .style('opacity', d => {
                if (window.shouldMuteNode && window.shouldMuteNode(d.data)) return 0.2;
                return 1;
            })
            .style('filter', d => d.data.is_searched_account ? 'drop-shadow(0 0 8px #00ffff)' : 'none');

        // Dense sibling rings: slightly smaller labels so arcs stay readable
        const labelPx = maxSiblingsAtDepth > 48
            ? Math.max(11, RADIAL_TEXT_SIZE - 4)
            : maxSiblingsAtDepth > 24
                ? Math.max(13, RADIAL_TEXT_SIZE - 2)
                : RADIAL_TEXT_SIZE;

        node.append('text')
            .attr('dy', '.31em')
            .attr('x', d => d.x < Math.PI ? 12 : -12)
            .attr('text-anchor', d => d.x < Math.PI ? 'start' : 'end')
            .attr('transform', d => d.x >= Math.PI ? 'rotate(180)' : null)
            .text(d => {
                if (d.data.stellar_account && d.data.node_type === 'ISSUER') {
                    return d.data.stellar_account.slice(-7);
                }
                return d.data.asset_code || d.data.name || 'Unnamed';
            })
            .style('fill', 'white')
            .style('font-size', labelPx + 'px')
            .style('font-weight', '500')
            .style('text-shadow', '1px 1px 2px rgba(0,0,0,0.8)')
            .style('pointer-events', 'none')
            .style('opacity', d => {
                if (window.shouldMuteNode && window.shouldMuteNode(d.data)) return 0.15;
                return 1;
            });

        function getPathToRoot(hierarchyNode) {
            const path = [];
            let current = hierarchyNode;
            while (current) {
                path.unshift(current);
                current = current.parent;
            }
            return path;
        }

        function linkKey(sourceData, targetData) {
            const s = sourceData.stellar_account || sourceData.asset_code || sourceData.name || 'root';
            const t = targetData.stellar_account || targetData.asset_code || targetData.name || 'node';
            return s + '_' + t;
        }

        function restoreLinkStyles() {
            link.each(function (d) {
                const linkElement = d3.select(this);
                if (d.target.data && d.target.data.is_lineage_path) {
                    linkElement
                        .style('stroke', '#ff3366')
                        .style('stroke-width', '2.5px')
                        .style('opacity', 0.9)
                        .style('filter', 'none');
                } else if (d.target.data && d.target.data.is_sibling) {
                    linkElement
                        .style('stroke', '#888888')
                        .style('stroke-width', '1.5px')
                        .style('opacity', 0.5)
                        .style('filter', 'none');
                } else {
                    linkElement
                        .style('stroke', '#3f2c70')
                        .style('stroke-width', '1.5px')
                        .style('opacity', 0.6)
                        .style('filter', 'none');
                }
            });
        }

        function highlightPath(pathToRoot) {
            const pathLinks = new Set();
            for (let i = 1; i < pathToRoot.length; i++) {
                pathLinks.add(linkKey(pathToRoot[i - 1].data, pathToRoot[i].data));
            }
            link.style('stroke', linkData => {
                const id = linkKey(linkData.source.data, linkData.target.data);
                if (pathLinks.has(id)) return '#ff0000';
                if (linkData.target.data && linkData.target.data.is_lineage_path) return '#ff3366';
                if (linkData.target.data && linkData.target.data.is_sibling) return '#888888';
                return '#3f2c70';
            })
            .style('stroke-width', linkData => {
                const id = linkKey(linkData.source.data, linkData.target.data);
                if (pathLinks.has(id)) return '3px';
                return (linkData.target.data && linkData.target.data.is_lineage_path) ? '2.5px' : '1.5px';
            })
            .style('opacity', linkData => {
                const id = linkKey(linkData.source.data, linkData.target.data);
                if (pathLinks.has(id)) return 1;
                return (linkData.target.data && linkData.target.data.is_lineage_path) ? 0.9 : 0.25;
            });
        }

        let selectedNode = null;

        function markSelected(d) {
            node.classed('node-selected', n => n === d);
            node.select('circle')
                .style('stroke-width', n => {
                    if (n === d) return '5px';
                    return n.data.is_searched_account ? '4px' : '2px';
                })
                .style('filter', n => {
                    if (n === d) return 'drop-shadow(0 0 10px #0BE784)';
                    return n.data.is_searched_account ? 'drop-shadow(0 0 8px #00ffff)' : 'none';
                });
        }

        function selectNode(d) {
            selectedNode = d;
            window.__smSelectedTreeNode = d;
            const pathToRoot = getPathToRoot(d);
            highlightPath(pathToRoot);
            markSelected(d);
            renderTreeBreadcrumbs(pathToRoot);
            renderTreePropertiesPane(d);
        }

        function clearSelection() {
            selectedNode = null;
            window.__smSelectedTreeNode = null;
            restoreLinkStyles();
            node.classed('node-selected', false);
            node.select('circle')
                .style('stroke-width', n => n.data.is_searched_account ? '4px' : '2px')
                .style('filter', n => n.data.is_searched_account ? 'drop-shadow(0 0 8px #00ffff)' : 'none');
            clearTreeSelectionUI();
        }

        node.on('click', function (event, d) {
            event.preventDefault();
            event.stopPropagation();
            if (selectedNode === d) {
                clearSelection();
            } else {
                selectNode(d);
            }
        });

        // Background click clears selection (not when interacting with chrome)
        svg.on('click.clear-selection', function (event) {
            if (event.target === svg.node()) {
                clearSelection();
            }
        });

        const closeBtn = document.getElementById('sm-tree-props-close');
        if (closeBtn && !closeBtn.__smBound) {
            closeBtn.__smBound = true;
            closeBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                if (typeof window.__smClearTreeSelection === 'function') {
                    window.__smClearTreeSelection();
                }
            });
        }
        window.__smClearTreeSelection = clearSelection;

        if (debugRadial) {
            console.log('Radial tree rendered', {
                nodes: totalNodeCount,
                maxSiblingsAtDepth,
                radius,
                size
            });
        }
        
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

// --- Radial chrome + non-overlap helpers (HTML overlays live outside SVG) ---

function ensureTreeChrome() {
    const host = document.getElementById('radial-tree-container');
    if (!host) return;

    // Host must be the positioning context (not flex-centered with the SVG)
    host.style.position = 'relative';
    host.style.display = 'block';
    host.style.overflow = 'hidden';

    let crumbs = document.getElementById('sm-tree-breadcrumbs');
    if (!crumbs) {
        crumbs = document.createElement('nav');
        crumbs.id = 'sm-tree-breadcrumbs';
        crumbs.className = 'sm-tree-breadcrumbs';
        crumbs.setAttribute('aria-label', 'Node path');
        crumbs.hidden = true;
        host.appendChild(crumbs);
    }
    let pane = document.getElementById('sm-tree-props');
    if (!pane) {
        pane = document.createElement('aside');
        pane.id = 'sm-tree-props';
        pane.className = 'sm-tree-props sm-tree-props--issuer';
        pane.setAttribute('aria-label', 'Node properties');
        pane.hidden = true;
        pane.innerHTML =
            '<div class="sm-tree-props__header">' +
            '<h3 class="sm-tree-props__title">Properties</h3>' +
            '<button type="button" class="sm-tree-props__close" id="sm-tree-props-close" aria-label="Close properties">×</button>' +
            '</div><div id="sm-tree-props-body" class="sm-tree-props__body"></div>';
        host.appendChild(pane);
    }

    // Always re-parent as direct children of the host AFTER the SVG so they
    // stay outside the zoom/pan transform and above the canvas.
    const svg = host.querySelector('svg#tree');
    if (crumbs.parentNode !== host) host.appendChild(crumbs);
    if (pane.parentNode !== host) host.appendChild(pane);
    if (svg) {
        // Keep SVG first for paint order; overlays last => on top
        if (svg.nextSibling !== crumbs) host.insertBefore(svg, host.firstChild);
        host.appendChild(crumbs);
        host.appendChild(pane);
    }

    // Inline pin (beats stray flex/center rules from older CSS)
    crumbs.style.position = 'absolute';
    crumbs.style.top = '10px';
    crumbs.style.left = '10px';
    crumbs.style.right = 'auto';
    crumbs.style.bottom = 'auto';
    crumbs.style.zIndex = '30';
    crumbs.style.transform = 'none';
    crumbs.style.margin = '0';

    pane.style.position = 'absolute';
    pane.style.top = '12px';
    pane.style.right = '12px';
    pane.style.left = 'auto';
    pane.style.bottom = 'auto';
    pane.style.zIndex = '30';
    pane.style.transform = 'none';
    pane.style.margin = '0';
}

function clearTreeSelectionUI() {
    const crumbs = document.getElementById('sm-tree-breadcrumbs');
    if (crumbs) {
        crumbs.innerHTML = '';
        crumbs.classList.remove('is-visible');
        crumbs.hidden = true;
        crumbs.style.display = 'none';
        crumbs.style.visibility = 'hidden';
    }
    const pane = document.getElementById('sm-tree-props');
    if (pane) {
        pane.classList.remove('is-visible', 'sm-tree-props--asset', 'sm-tree-props--issuer');
        pane.hidden = true;
        pane.style.display = 'none';
        pane.style.visibility = 'hidden';
    }
    const body = document.getElementById('sm-tree-props-body');
    if (body) body.innerHTML = '';
    // Orphan body tooltips from older tidy/hover path
    try { d3.selectAll('body > .tooltip').style('opacity', 0).remove(); } catch (e) {}
}

function nodeDisplayLabel(data, opts) {
    opts = opts || {};
    if (!data) return 'Root';
    if (data.stellar_account && data.node_type === 'ISSUER') {
        return opts.full ? data.stellar_account : data.stellar_account.slice(-7);
    }
    if (data.stellar_account && opts.full) return data.stellar_account;
    if (data.stellar_account && !opts.full && data.stellar_account.length > 12) {
        return data.stellar_account.slice(0, 4) + '…' + data.stellar_account.slice(-4);
    }
    return data.asset_code || data.name || data.stellar_account || 'Root';
}

function renderTreeBreadcrumbs(pathToRoot) {
    ensureTreeChrome();
    const crumbs = document.getElementById('sm-tree-breadcrumbs');
    if (!crumbs) return;
    crumbs.innerHTML = '';
    pathToRoot.forEach(function (n, i) {
        if (i > 0) {
            const sep = document.createElement('span');
            sep.className = 'sm-tree-breadcrumbs__sep';
            sep.textContent = '›';
            sep.setAttribute('aria-hidden', 'true');
            crumbs.appendChild(sep);
        }
        const chip = document.createElement('span');
        chip.className = 'sm-tree-breadcrumbs__chip';
        if (n.data && n.data.node_type === 'ASSET') {
            chip.classList.add('sm-tree-breadcrumbs__chip--asset');
        } else {
            chip.classList.add('sm-tree-breadcrumbs__chip--issuer');
        }
        if (i === pathToRoot.length - 1) {
            chip.classList.add('sm-tree-breadcrumbs__chip--active');
        }
        chip.textContent = nodeDisplayLabel(n.data, { full: false });
        chip.title = nodeDisplayLabel(n.data, { full: true });
        crumbs.appendChild(chip);
    });
    crumbs.hidden = false;
    crumbs.style.display = '';
    crumbs.style.visibility = 'visible';
    crumbs.classList.add('is-visible');
}

function formatTreeNumber(value) {
    const n = parseFloat(value || 0);
    if (isNaN(n)) return '0';
    return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function renderTreePropertiesPane(hierarchyNode) {
    ensureTreeChrome();
    const pane = document.getElementById('sm-tree-props');
    const body = document.getElementById('sm-tree-props-body');
    if (!pane || !body || !hierarchyNode) return;

    const d = hierarchyNode.data || {};
    const isAsset = d.node_type === 'ASSET';

    // Match original floating tooltip field order and <b>Label:</b> value formatting
    let html = '';
    function line(label, value) {
        if (value === undefined || value === null || value === '') value = 'N/A';
        html += '<span class="sm-tree-props__line"><b>' + escapeHtml(label) + ':</b> ' +
            escapeHtml(String(value)) + '</span>';
    }

    line('Name', d.stellar_account || d.asset_code || d.name || 'Unnamed');
    if (isAsset) {
        line('Issuer', d.asset_issuer);
        line('Asset Type', d.asset_type);
        line('Balance', formatTreeNumber(d.balance));
    } else {
        line('Created', d.created);
        line('Home Domain', d.home_domain);
        line('XLM Balance', formatTreeNumber(d.xlm_balance));
        line('Creator', d.creator_account);
    }

    body.innerHTML = html;
    const titleEl = pane.querySelector('.sm-tree-props__title');
    if (titleEl) {
        titleEl.textContent = isAsset ? 'Asset' : 'Account';
        titleEl.style.display = 'block';
    }
    pane.classList.remove('sm-tree-props--asset', 'sm-tree-props--issuer');
    pane.classList.add(isAsset ? 'sm-tree-props--asset' : 'sm-tree-props--issuer');
    pane.hidden = false;
    pane.style.display = '';
    pane.style.visibility = 'visible';
    pane.classList.add('is-visible');
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

/**
 * Push nodes apart so circle centers keep min distance (no node-on-node overlap).
 * Operates in polar space per depth ring, then verifies cartesian distance.
 */
function resolveRadialNodeOverlaps(descendants, opts) {
    opts = opts || {};
    const nodeR = opts.nodeRadius || RADIAL_NODE_SIZE;
    const minGap = opts.minGap != null ? opts.minGap : 8;
    const minDist = nodeR * 2 + minGap;
    const minRadialStep = opts.minRadialStep || (minDist + 4);
    const TWO_PI = 2 * Math.PI;

    const byDepth = new Map();
    descendants.forEach(function (d) {
        if (!byDepth.has(d.depth)) byDepth.set(d.depth, []);
        byDepth.get(d.depth).push(d);
    });
    const depths = Array.from(byDepth.keys()).sort(function (a, b) { return a - b; });

    let prevRadius = 0;
    depths.forEach(function (depth) {
        const nodes = byDepth.get(depth);
        if (depth === 0) {
            nodes.forEach(function (d) { d.y = 0; d.x = 0; });
            prevRadius = 0;
            return;
        }

        // Radius: keep layout y but never closer than minRadialStep to previous ring
        let ringR = 0;
        nodes.forEach(function (d) { if (d.y > ringR) ringR = d.y; });
        ringR = Math.max(ringR, prevRadius + minRadialStep);

        // Angular budget: enough circumference for all nodes on this ring
        const n = nodes.length;
        const needR = (n * minDist) / TWO_PI;
        ringR = Math.max(ringR, needR);
        nodes.forEach(function (d) { d.y = ringR; });

        // Preserve order; enforce min angular separation (including wrap-around)
        nodes.sort(function (a, b) { return a.x - b.x; });
        const minAngle = minDist / Math.max(ringR, 1);

        if (n * minAngle >= TWO_PI * 0.98) {
            // Fully packed: even spacing around the circle
            nodes.forEach(function (d, i) {
                d.x = (i / n) * TWO_PI;
            });
        } else {
            // Forward pass
            for (let i = 1; i < n; i++) {
                if (nodes[i].x - nodes[i - 1].x < minAngle) {
                    nodes[i].x = nodes[i - 1].x + minAngle;
                }
            }
            // If we overflowed past 2π, compact then re-center into [0, 2π)
            let span = nodes[n - 1].x - nodes[0].x;
            if (nodes[n - 1].x - nodes[0].x > TWO_PI - minAngle) {
                nodes.forEach(function (d, i) {
                    d.x = (i / n) * TWO_PI;
                });
            } else {
                // Wrap-around gap between last and first
                const wrapGap = (nodes[0].x + TWO_PI) - nodes[n - 1].x;
                if (wrapGap < minAngle) {
                    // Shift pack so wrap gap is satisfied, or even-space
                    const needed = minAngle - wrapGap;
                    if (span + needed <= TWO_PI) {
                        // shrink from the end by spreading earlier... simpler: even space
                        nodes.forEach(function (d, i) {
                            d.x = (i / n) * TWO_PI;
                        });
                    } else {
                        nodes.forEach(function (d, i) {
                            d.x = (i / n) * TWO_PI;
                        });
                    }
                } else if (nodes[0].x < 0 || nodes[n - 1].x > TWO_PI) {
                    const shift = nodes[0].x;
                    nodes.forEach(function (d) {
                        d.x = ((d.x - shift) % TWO_PI + TWO_PI) % TWO_PI;
                    });
                    nodes.sort(function (a, b) { return a.x - b.x; });
                }
            }
        }
        prevRadius = ringR;
    });

    // Final cartesian pass: if any pair still too close, nudge outer node outward
    function polarToXY(d) {
        return {
            x: d.y * Math.cos(d.x - Math.PI / 2),
            y: d.y * Math.sin(d.x - Math.PI / 2)
        };
    }
    for (let pass = 0; pass < 3; pass++) {
        let moved = false;
        for (let i = 0; i < descendants.length; i++) {
            for (let j = i + 1; j < descendants.length; j++) {
                const a = descendants[i];
                const b = descendants[j];
                if (a.depth === 0 || b.depth === 0) continue;
                const pa = polarToXY(a);
                const pb = polarToXY(b);
                const dx = pa.x - pb.x;
                const dy = pa.y - pb.y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 0.0001;
                if (dist < minDist) {
                    const outer = a.y >= b.y ? a : b;
                    outer.y += (minDist - dist) + 2;
                    moved = true;
                }
            }
        }
        if (!moved) break;
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