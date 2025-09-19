// webApp/static/webApp/js/lineage_table_mixin.js
const lineage_table_mixin = {
  data() {
      return {
          transProps: {
              name: 'flip-list'
          },
          account_genealogy_items: [],
          account_genealogy_fields: [
              { key: 'index', label: 'Index', sortable: true, visible: true },
              { key: 'stellar_creator_account', label: 'Creator Account', sortable: true, visible: false },
              { key: 'stellar_account_created_at', label: 'Account Created At', sortable: true, visible: true },
              { key: 'stellar_account', label: 'Account', sortable: true, visible: true },
              { key: 'network_name', label: 'Network Name', sortable: true, visible: true },
              { key: 'home_domain', label: 'Home Domain', sortable: true, visible: true },
              { key: 'xlm_balance', label: 'XLM Balance', sortable: true, visible: true },
              { key: 'stellar_expert', label: 'Stellar Expert', sortable: true, visible: true },
              { key: 'horizon_account_assets', label: 'Assets', sortable: false, visible: true }, // Added
              { key: 'stellar_expert_directory', label: 'Expert Directory', sortable: false, visible: true }, // Added
              { key: 'horizon_account_flags', label: 'Flags', sortable: false, visible: true }, // Added
              { key: 'status', label: 'Status', sortable: true, visible: true },
              { key: 'updated_at', label: 'Updated At', sortable: true, visible: true }
          ],
          apiStellarExpertTagsResponses: [],
          tree_genealogy_items: null,
          smrt_treeGenealogyItems: null,
          smrt_tooltip: null,
          smrt_navbars: null,
          smrt_diameter: 570,
          smrt_width: null,
          smrt_height: null,
          smrt_counter: 0,
          smrt_duration: 350,
          smrt_root: null,
          smrt_tree: null,
          smrt_filteredPartition: null,
          smrt_radialProjection: null,
          smrt_svg: null,
          smrt_color: null,
          smrt_legend: null,
          smrt_angle: 0,
          smrt_buttons: null
      };
  },
  mounted() {
      if (typeof d3 !== 'undefined') {
          this.smrt_treeGenealogyItems = JSON.parse(JSON.stringify(this.tree_genealogy_items));
          this.smrt_tooltip = d3.select('#display_radial_tidy_tree')
              .append('div')
              .attr('class', 'tooltip')
              .style('opacity', 0)
              .style('left', '0px')
              .style('top', '0px');
          this.smrt_navbars = d3.select('div.b')
              .append('nav')
              .attr('class', 'breadcrumbs');
          this.smrt_width = this.smrt_diameter;
          this.smrt_height = this.smrt_diameter;
          this.smrt_root = d3.hierarchy(this.smrt_treeGenealogyItems || { name: "Root", children: [] });
          this.smrt_root.x0 = this.smrt_height / 2;
          this.smrt_root.y0 = 0;
          this.smrt_tree = d3.tree()
              .size([360, this.smrt_diameter / 2])
              .separation(function(a, b) {
                  return (a.parent == b.parent ? 1 : 1.5) / a.depth;
              });
          this.smrt_filteredPartition = d3.partition()
              .size([2 * Math.PI, this.smrt_diameter / 2])
              .value(function(d) { return d.value || 1; })
              .padding(1);
          this.smrt_radialProjection = d3.linkRadial()
              .angle(function(d) { return d.x; })
              .radius(function(d) { return d.y; });
          this.smrt_svg = d3.select('#display_radial_tidy_tree').append('svg')
              .attr('preserveAspectRatio', 'xMinYMin meet')
              .attr('viewBox', '0 0 ' + this.smrt_width + ' ' + this.smrt_height)
              .append('g')
              .attr('transform', 'translate(' + this.smrt_diameter / 2 + ',' + this.smrt_diameter / 2 + ') rotate(0)');
          this.smrt_color = d3.scaleOrdinal(['#3f2c70', '#fcec04']);
          this.smrt_legend = d3.select('body svg').append('g').attr('class', 'legend');
          this.smrt_angle = 0;
          this.smrt_buttons = d3.select('body svg').append('g').attr('class', 'button');
          this.update(this.smrt_root);
      } else {
          console.warn('D3 is not loaded on this page, skipping radial tree initialization');
      }
  },
  methods: {
      getAccountGenealogy: async function(stellar_account, network_name) {
          try {
              console.log("Starting getAccountGenealogy for:", stellar_account, network_name);
              const csrf_token = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
              const headers = {
                  'Content-Type': 'application/json',
                  'X-CSRFToken': csrf_token
              };
              const url = `/api/account-genealogy/network/${network_name}/stellar_address/${stellar_account}/`;
              const genealogy_response = await fetch(url, { method: 'GET', headers });
              console.log("Fetch completed, status:", genealogy_response.status);
              if (!genealogy_response.ok) {
                  const errorText = await genealogy_response.text();
                  console.error(`Failed to fetch genealogy data: ${genealogy_response.status} - ${errorText}`);
                  Sentry.captureException(new Error(`HTTP ${genealogy_response.status}: ${errorText}`));
                  throw new Error(`Failed to fetch genealogy data: ${genealogy_response.status}`);
              }
              const responseJson = await genealogy_response.json();
              console.log("Parsed response JSON:", responseJson);
              console.log("Response JSON type:", typeof responseJson);

              // If responseJson is a string, parse it again
              let parsedJson = responseJson;
              if (typeof responseJson === 'string') {
                  parsedJson = JSON.parse(responseJson);
                  console.log("Re-parsed response JSON:", parsedJson);
              }

              console.log("Response JSON keys:", Object.keys(parsedJson));
              console.log("Checking account_genealogy_items:", parsedJson.account_genealogy_items);
              const items = parsedJson.account_genealogy_items || [];
              console.log("Extracted items:", items);
              this.account_genealogy_items = items;
              console.log("Assigned items:", this.account_genealogy_items);
              this.tree_genealogy_items = parsedJson.tree_genealogy_items || null;
              console.log("Genealogy data loaded:", this.account_genealogy_items);
              this.$forceUpdate();
              console.log("Forced update, final items:", this.account_genealogy_items);
          } catch (e) {
              console.error("Error in getAccountGenealogy:", e);
              alert(e.message);
              Sentry.captureException(e);
          }
      },
      truncateStellarAccount(stellar_account) {
          if (stellar_account && stellar_account.length > 17) {
              return stellar_account.slice(0, 6) + '...' + stellar_account.slice(-6);
          } else {
              return stellar_account;
          }
      },
      viewExternalLinkStellarExpert(stellar_account, network_name) {
          const base_url = "https://stellar.expert/explorer/";
          return base_url.concat(network_name, '/account/', stellar_account);
      },
      viewTooltipString(string_name) {
          return string_name;
      },
      viewExternalLinkTOML(home_domain) {
          const base_url = "https://";
          return base_url.concat(home_domain, '/.well-known/stellar.toml');
      },
      viewExternalLinkTOMLChecker(home_domain) {
          const base_url = "https://stellar.sui.li/";
          return base_url.concat(home_domain);
      },
      async getApiStellarExpertTags(row_index, stellar_account, network_name) {
          try {
            const base_url = "https://api.stellar.expert/explorer/";
            const url_path = base_url.concat(network_name, '/directory/', stellar_account);
            const response = await fetch(url_path);
            if (!response.ok) throw new Error('Failed to fetch tags');
            this.$set(this.apiStellarExpertTagsResponses, row_index, await response.json());
            return this.apiStellarExpertTagsResponses[row_index];
          } catch (e) {
            console.error('Error fetching Stellar Expert tags:', e);
            return null;
          }
      },
      formatHashtag(tag) {
          return '#' + tag;
      },
      update(source) {
          if (typeof d3 === 'undefined') return;
          var nodes = this.smrt_tree(source).descendants(),
              links = this.smrt_tree(source).links();
          nodes.forEach(function(d) { d.y = d.depth * 80; });
          var node = this.smrt_svg.selectAll("g.node")
              .data(nodes, function(d) { return d.id || (d.id = ++this.smrt_counter); });
          var nodeEnter = node.enter()
              .append("g")
              .attr("class", "node")
              .attr('name', d => d.data.deleted ? "DELETED" : d.data.node_type)
              .on("click", this.click)
              .on("mouseenter", this.mouseEnter)
              .on("mouseleave", this.mouseLeave);
          this.smrt_tooltip.on('mouseenter', this.tooltipMouseEnter)
              .on('mouseleave', this.tooltipMouseLeave);
          nodeEnter.append("circle")
              .attr("r", 1e-7)
              .on("mouseenter", this.circleMouseEnter);
          nodeEnter.append("text")
              .attr("x", function(d) { return d.x < 180 ? 6 : -6; })
              .attr("dy", "0.31em")
              .attr("text-anchor", function(d) { return d.x < 180 ? "start" : "end"; })
              .text(function(d) { return d.data.name; })
              .style("fill-opacity", 1e-6);
          var nodeUpdate = node.transition()
              .duration(this.smrt_duration)
              .attr("transform", function(d) { return "rotate(" + (d.x - 90) + ")translate(" + d.y + ")"; });
          nodeUpdate.select("circle")
              .attr("r", this.smrt_diameter / 300)
              .style("fill", function(d) { return d._children ? "#fff" : "#3f2c70"; })
              .style("stroke", function(d) {
                  if (d.data.node_type === 'ASSET') return '#fcec04';
                  return d.data.deleted ? '#cc3463' : '#00FF9C';
              });
          nodeUpdate.select("text")
              .style("fill-opacity", 1)
              .attr("transform", function(d) { return d.x < 180 ? "translate(0)" : "rotate(180)translate(-12)"; });
          var nodeExit = node.exit().transition()
              .duration(this.smrt_duration)
              .remove();
          nodeExit.select("circle")
              .attr("r", 1e-6);
          nodeExit.select("text")
              .style("fill-opacity", 1e-6);
          var link = this.smrt_svg.selectAll("path.link")
              .data(links, function(d) { return d.target.id; });
          link.enter().insert("path", "g")
              .attr("class", "link")
              .attr("id", function(d) { return "link" + d.source.id + "-" + d.target.id; })
              .attr("name", function(d) { return d.target.data.deleted ? "DELETED" : d.target.data.node_type; })
              .attr("d", function(d) {
                  var o = { x: source.x0, y: source.y0 };
                  return this.smrt_radialProjection({ source: o, target: o });
              });
          link.transition()
              .duration(this.smrt_duration)
              .attr("d", this.smrt_radialProjection);
          link.exit().transition()
              .duration(this.smrt_duration)
              .attr("d", function(d) {
                  var o = { x: source.x, y: source.y };
                  return this.smrt_radialProjection({ source: o, target: o });
              })
              .remove();
          nodes.forEach(function(d) {
              d.x0 = d.x;
              d.y0 = d.y;
          });
      },
      click(d) {
          if (d.children) {
              d._children = d.children;
              d.children = null;
          } else {
              d.children = d._children;
              d._children = null;
          }
          this.update(d);
      },
      mouseEnter(d) {
          if (typeof d3 === 'undefined') return;
          var lineage = [];
          var type = [];
          d3.selectAll("circle").style("fill", "#3f2c70");
          d3.selectAll("path").style("stroke", "#3f2c70");
          var current = d;
          while (current.parent) {
              d3.selectAll("#node" + current.id).style("fill", "red");
              d3.selectAll("circle").filter(d => d.id === current.id).style("fill", "red");
              if (current.parent.data) {
                  lineage.push(current.data.name);
                  type.push(current.data.node_type === 'ASSET' ? '#fcec04' : (current.data.deleted ? '#cc3463' : "#00FF9C"));
                  d3.selectAll("#link" + current.parent.id + "-" + current.id).style("stroke", "red");
              }
              current = current.parent;
          }
          for (var i = lineage.length - 1; i >= 0; i--) {
              this.smrt_navbars.append('a')
                  .attr('class', 'breadcrumbs__item')
                  .style('background', type[i])
                  .append('text')
                  .style('fill', 'black')
                  .text(lineage[i]);
          }
      },
      mouseLeave() {
          if (typeof d3 === 'undefined') return;
          this.smrt_tooltip.style("opacity", 0);
          d3.selectAll("circle").style("fill", "#3f2c70");
          d3.selectAll("path").style("stroke", "#3f2c70");
          d3.selectAll('.breadcrumbs__item').remove();
      },
      tooltipMouseEnter() {
          if (typeof d3 === 'undefined') return;
          d3.select(this).style("opacity", 1);
      },
      tooltipMouseLeave() {
          if (typeof d3 === 'undefined') return;
          d3.select(this).style("opacity", 0)
              .html("")
              .style("left", "0px")
              .style("top", "0px");
      },
      circleMouseEnter(d) {
          if (typeof d3 === 'undefined') return;
          if (d.data.node_type === 'ASSET') {
              this.smrt_tooltip.style("opacity", 0.71).style("background-color", '#fcec04')
                  .html("<b>Name:</b> " + (d.data.name || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;') + "<br><b>Issuer Id:</b> " + ((d.data.asset_issuer || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;')) +
                      "<br><b>Asset type:</b> " + (d.data.asset_type || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                      "<br><b>Asset Code:</b> " + (d.data.asset_code || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                      "<br><b>Asset Issuer:</b> " + (d.data.asset_issuer || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                      "<br><b>Balance:</b> " + (d.data.balance || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                      "<br><b>Limit:</b> " + (d.data.limit || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                      "<br><b>Is Authorized:</b> " + (d.data.is_authorized || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                      "<br><b>Is Authorized To Maintain Liabilities:</b> " + (d.data.is_authorized_to_maintain_liabilities || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                      "<br><b>Is Clawback Enabled:</b> " + (d.data.is_clawback_enabled || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                      "<br><b>Stellar Expert:</b> <a href='" + (d.data.stellar_expert || '#') + "'>Link</a>" +
                      "<br><b>Number of Accounts:</b> " + (d.data.num_accounts || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                      "<br><b>Number of Claimable Balances:</b> " + (d.data.num_claimable_balances || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                      "<br><b>Num of Liquidity Pools:</b> " + (d.data.num_liquidity_pools || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                      "<br><b>Amount:</b> " + (d.data.amount || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;'))
                  .style("left", (d3.event.pageX) + "px")
                  .style("top", (d3.event.pageY) + "px");
          } else {
              this.smrt_tooltip.style("opacity", 0.71).style("background-color", d.data.deleted ? '#cc3463' : '#00FF9C')
                  .html("<b>Stellar Account:</b> " + ((d.data.stellar_account || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;')) +
                      "<br><b>Created:</b> " + ((d.data.created || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;')) +
                      "<br><b>Creator Account:</b> " + ((d.data.home_domain || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;')) +
                      "<br><b>Home Domain:</b> " + ((d.data.home_domain || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;')) +
                      "<br><b>XLM Balance:</b> " + ((d.data.xlm_balance || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;')))
                  .style("left", (d3.event.pageX) + "px")
                  .style("top", (d3.event.pageY) + "px");
          }
          if (d.x < 90 && d.x > 0) {
              this.smrt_tooltip.style("left", (d3.event.pageX - this.smrt_tooltip.node().offsetWidth) + "px");
          } else if (d.x < 180 && d.x > 90) {
              this.smrt_tooltip.style("left", (d3.event.pageX - this.smrt_tooltip.node().offsetWidth) + "px")
                  .style("top", (d3.event.pageY - this.smrt_tooltip.node().offsetHeight) + "px");
          } else if (d.x < 270 && d.x > 180) {
              this.smrt_tooltip.style("top", (d3.event.pageY - this.smrt_tooltip.node().offsetHeight) + "px");
          }
      },
      collapse(d) {
          if (d.children) {
              d._children = d.children;
              d._children.forEach(this.collapse);
              d.children = null;
          }
      }
  },
  computed: {
      visibleGeneologyFields() {
          return this.account_genealogy_fields.filter(field => field.visible);
      }
  },
  watch: {
      account_genealogy_items: {
          deep: true,
          handler(newVal, oldVal) {
              if (newVal !== oldVal) {
                  newVal.forEach((item) => {
                      this.getApiStellarExpertTags(item.index, item.stellar_account, item.network_name);
                  });
              }
          }
      }
  }
};
