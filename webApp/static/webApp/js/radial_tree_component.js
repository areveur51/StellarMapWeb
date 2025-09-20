// webApp/static/webApp/js/radial_tree_component.js
/**
 * Radial Tree Vue Component
 * Renders a radial tree using D3.js.
 * Efficiency: Re-renders only on prop change; clears old SVG.
 * Readability: Clear methods with comments.
 * Security: No direct DOM injections; assumes secure treeData (validate upstream).
 * Documentation: JSDoc for component/methods.
 */

Vue.component('radial-tree', {
    template: '<div ref="treeContainer" class="radial-tree-container"></div>',
    props: {
        treeData: {
            type: Object,
            required: true  // Enforce prop for safety
        }
    },
    mounted: function() {
        this.renderTree();
    },
    watch: {
        treeData: function(newData) {
            // Efficient: Re-render only on data change
            this.renderTree();
        }
    },
    methods: {
        /**
         * Render the radial tree.
         * Assumes global renderRadialTree function (from external D3 script).
         */
        renderTree: function() {
            if (!this.treeData) {
                console.warn("No tree data provided.");
                return;
            }
            console.log("Rendering tree with data:", this.treeData);

            // Clear previous content to prevent overlaps/leaks
            const container = this.$refs.treeContainer;
            while (container.firstChild) {
                container.removeChild(container.firstChild);
            }

            // Call external render function (assume it's secure)
            renderRadialTree(container, this.treeData);
        }
    }
});