(function () {
  var map = document.querySelector("[data-decision-map]");
  if (!map) return;

  var form = map.querySelector("[data-decision-controls]");
  var result = map.querySelector("[data-decision-result]");
  var nodes = Array.prototype.slice.call(map.querySelectorAll("[data-checkpoint-node]"));
  var rails = Array.prototype.slice.call(map.querySelectorAll("[data-terminal-rail]"));

  function selected(name) {
    var input = form.querySelector('input[name="' + name + '"]:checked');
    return input ? input.value : "";
  }

  function gateList(node, attribute) {
    return (node.getAttribute(attribute) || "").split(/\s+/).filter(Boolean);
  }

  function nodeName(node) {
    var heading = node.querySelector("h4");
    return heading ? heading.textContent.trim() : "checkpoint";
  }

  function setNodeState(compatible, fastest, filterActive) {
    nodes.forEach(function (node) {
      var isCompatible = compatible.indexOf(node) !== -1;
      var state = node.querySelector("[data-node-state]");
      node.classList.toggle("is-compatible", isCompatible);
      node.classList.toggle("is-muted", filterActive && !isCompatible);
      node.classList.toggle("is-fastest", node === fastest);
      if (node.parentElement) node.parentElement.classList.toggle("has-compatible", filterActive && isCompatible);
      if (state) {
        state.textContent = !filterActive ? "" : node === fastest
          ? "Fastest compatible live reading for the selected route and lane."
          : isCompatible
            ? "Compatible with the selected route."
            : "Not compatible with the selected route.";
      }
    });
    rails.forEach(function (rail) {
      var hasCompatible = compatible.some(function (node) { return rail.contains(node); });
      rail.classList.toggle("has-compatible", filterActive && hasCompatible);
    });
  }

  function update() {
    var gate = selected("decision-gate");
    var lane = selected("decision-lane") || "standard";
    var terminal = selected("decision-terminal");
    var compatible = [];
    var allowRecommendation = true;
    var message = "Choose a gate to highlight compatible checkpoints.";

    if (!gate) {
      compatible = terminal
        ? nodes.filter(function (node) { return node.dataset.terminal === terminal; })
        : [];
      message = terminal
        ? "Showing checkpoints published for " + (terminal === "t1" ? "Terminal 1." : "Terminal 3.")
        : message;
      allowRecommendation = false;
    } else {
      var conflict = (terminal === "t3" && /^(A|B|C)$/.test(gate)) ||
        (terminal === "t1" && gate === "E");
      if (conflict) {
        setNodeState([], null, true);
        result.textContent = "That gate and terminal combination does not match this routing map. Recheck the terminal on your boarding pass.";
        return;
      }

      compatible = nodes.filter(function (node) {
        return gateList(node, "data-compatible-gates").indexOf(gate) !== -1 &&
          (!terminal || node.dataset.terminal === terminal);
      });

      if (gate === "D" && !terminal) {
        message = "Gate D can route through Terminal 1 or Terminal 3. Choose your check-in terminal to compare the right checkpoint.";
        allowRecommendation = false;
      }
    }

    var waitAttribute = lane === "precheck" ? "data-precheck-wait" : "data-standard-wait";
    var ranked = compatible.map(function (node, index) {
      var raw = node.getAttribute(waitAttribute);
      return {
        node: node,
        wait: raw === "" ? NaN : Math.round(Number(raw)),
        primary: gateList(node, "data-primary-gates").indexOf(gate) !== -1 ? 0 : 1,
        index: index
      };
    }).filter(function (item) {
      return Number.isFinite(item.wait);
    }).sort(function (a, b) {
      return (a.wait - b.wait) || (a.primary - b.primary) || (a.index - b.index);
    });

    var fastest = allowRecommendation && ranked.length ? ranked[0] : null;
    setNodeState(compatible, fastest ? fastest.node : null, Boolean(gate || terminal));

    if (fastest) {
      var laneLabel = lane === "precheck" ? "PreCheck" : "standard";
      message = "Fastest compatible live reading: " + nodeName(fastest.node) +
        ", " + Math.round(fastest.wait) + " minutes for " + laneLabel + ".";
    } else if (allowRecommendation && compatible.length) {
      message = "The compatible checkpoints are highlighted, but no fresh " +
        (lane === "precheck" ? "PreCheck" : "standard") + " reading is available.";
    }

    result.textContent = message;
  }

  form.addEventListener("change", update);
  update();
})();
