// webApp/static/webApp/js/radial_tree_component.js
Vue.component('radial-tree', {
    template: '<div ref="treeContainer" class="radial-tree-container"></div>',
    props: ['treeData'],
    mounted: function() {
      this.renderTree();
    },
    watch: {
      treeData: function(newData) {
        this.renderTree();
      }
    },
    methods: {
      renderTree: function() {
        if (this.treeData) {
          console.log("Rendering tree with data:", this.treeData);
          renderRadialTree(this.$refs.treeContainer, this.treeData);
        }
      }
    }
  });
