"""Behavior checks for terminal-specific planning and honest history rendering."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("node"), "Node is needed to execute the browser scripts")
class AirportFlowBehaviorTests(unittest.TestCase):
    def run_node(self, source):
        result = subprocess.run(["node", "-e", source], cwd=ROOT, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def render_history(self, payload, ok=True):
        return self.run_node("""
const fs = require('fs'), vm = require('vm');
const mount = {dataset: {airport:'LAX'}, innerHTML:''};
const payload = %s;
vm.runInNewContext(fs.readFileSync('static/forecast-chart.js','utf8'), {
  document: {getElementById: () => mount},
  fetch: async () => ({ok:%s,json:async () => payload})
});
setImmediate(() => process.stdout.write(JSON.stringify(mount.innerHTML)));
""" % (json.dumps(payload), str(ok).lower()))

    def test_missing_history_renders_no_zero_or_forecast(self):
        html = self.render_history({"hours": [{"hour": h, "standard": None, "precheck": None} for h in range(24)]})
        self.assertIn("No historical observations", html)
        self.assertNotIn("<svg", html)
        self.assertNotIn("NOW", html)
        self.assertNotIn("BEST", html)
        self.assertNotIn("predicted", html)
        self.assertIn("No observations", html)

    def test_sparse_history_breaks_path_and_preserves_real_zero(self):
        html = self.render_history({"timezone": "America/New_York", "hours": [
            {"hour": 0, "standard": 0, "precheck": None, "standardSamples": 4},
            {"hour": 2, "standard": 30, "precheck": 5, "standardSamples": 2, "precheckSamples": 3}
        ]})
        self.assertIn("<td>0 min</td><td>4</td>", html)
        self.assertIn("Standard: 2/24", html)
        self.assertIn("PreCheck: 1/24", html)
        self.assertIn("America/New_York", html)
        self.assertIn('scope="col"', html)
        # Missing hour 1 must start a new segment rather than connect hour 0 to 2.
        self.assertRegex(html, r'<path d="M[^"L]*M[^"L]*"')

    def test_history_error_is_visible(self):
        html = self.render_history({}, ok=False)
        self.assertIn('role="status"', html)
        self.assertIn("unavailable right now", html)

    def run_selection(self, query="", change_terminal=None, minutes_old=1):
        return self.run_node("""
const fs = require('fs'), vm = require('vm');
function element(extra={}) { return Object.assign({textContent:'',innerHTML:'',className:'',dataset:{},hidden:false,attrs:{},events:{},classList:{toggle(){},remove(){},add(){}},setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,v){this.events[k]=v;}},extra); }
const model = {airport:{code:'JFK'},decision_mode:'terminal_checkpoint',freshness_rules:{max_current_minutes:15},terminals:[
 {id:'t1',label:'Terminal 1',checkpoints:[{id:'jfk-t1',label:'Terminal 1 checkpoint',lanes:[{lane_type:'STANDARD',wait_minutes:30,freshness_status:'live',captured_at:new Date(Date.now()-%s*60000).toISOString()},{lane_type:'PRECHECK',wait_minutes:8,freshness_status:'live',captured_at:new Date().toISOString()}]}]},
 {id:'t4',label:'Terminal 4',checkpoints:[{id:'jfk-t4',label:'Terminal 4 checkpoint',lanes:[{lane_type:'STANDARD',wait_minutes:2,freshness_status:'live',captured_at:new Date().toISOString()}]}]}
]};
const selections = {'decision-terminal':'','decision-lane':'STANDARD','decision-gate':''};
const radios = Object.fromEntries(Object.entries({'decision-terminal':['','t1','t4'],'decision-lane':['STANDARD','PRECHECK'],'decision-gate':['']} ).map(([name,values])=>[name,values.map(value=>({value,get checked(){return selections[name]===value;},set checked(v){if(v)selections[name]=value;}}))]));
const form = element({querySelector(s){const m=s.match(/name="([^"]+)"/);return m?radios[m[1]].find(x=>x.checked):null;},querySelectorAll(s){const m=s.match(/name="([^"]+)"/);return m?radios[m[1]]:[];}});
const items=model.terminals.map(t=>element({dataset:{checkpointId:t.checkpoints[0].id,terminal:t.id},getAttribute(){return '';},querySelector(){return element();},querySelectorAll(){return [];}}));
const controls={
 '[data-decision-controls]':form,'[data-decision-result]':element(),
 '[data-arrival-calculator-link]':element(),'[data-arrival-plan-label]':element(),'[data-arrival-plan-note]':element(),
 '[data-arrival-current-label]':element(),'[data-arrival-current-wait]':element(),'[data-arrival-current-source]':element(),'[data-arrival-current-trend]':element(),
 '[data-airport-map-details]':element({open:false})
};
const root=element({dataset:{airportCode:'JFK'},querySelector:s=>controls[s]||null,querySelectorAll:s=>s==='[data-arrival-checkpoint-item]'?items:[],contains:()=>false});
const noop=()=>{};
const window={location:{search:%s},matchMedia:()=>({matches:false,addEventListener:noop}),sessionStorage:{getItem:()=>null},requestAnimationFrame:noop,setInterval:noop,clearInterval:noop,setTimeout:noop,addEventListener:noop};
const document={querySelector:s=>s==='[data-airport-arrival-mode]'?root:null,getElementById:id=>id==='airport-arrival-mode-data'?{textContent:JSON.stringify(model)}:null,addEventListener:noop,body:{classList:{toggle:noop}}};
vm.runInNewContext(fs.readFileSync('static/airport-decision-map.js','utf8'),{window,document,URLSearchParams,Date});
const nextTerminal=%s;
if(nextTerminal!==null){selections['decision-terminal']=nextTerminal;form.events.change({target:{name:'decision-terminal',value:nextTerminal}});}
process.stdout.write(JSON.stringify({summary:controls['[data-arrival-current-wait]'].innerHTML,message:controls['[data-decision-result]'].textContent,href:controls['[data-arrival-calculator-link]'].href,label:controls['[data-arrival-plan-label]'].textContent,hidden:items.map(x=>x.hidden)}));
""" % (minutes_old, json.dumps(query), json.dumps(change_terminal)))

    def test_terminal_is_required_before_fastest_recommendation(self):
        result = self.run_selection()
        self.assertIn("Select a terminal first", result["summary"])
        self.assertNotIn("Fastest", result["message"])
        self.assertNotIn("checkpoint=", result["href"])
        self.assertEqual(result["label"], "Plan with a security allowance")

    def test_terminal_filter_excludes_faster_disconnected_terminal(self):
        result = self.run_selection(change_terminal="t1")
        self.assertIn("30<small>", result["summary"])
        self.assertIn("checkpoint=jfk-t1", result["href"])
        self.assertIn("terminal=t1", result["href"])
        self.assertEqual(result["hidden"], [False, True])

    def test_deep_link_preserves_terminal_and_precheck(self):
        result = self.run_selection(query="?terminal=t1&lane=PRECHECK")
        self.assertIn("8<small>", result["summary"])
        self.assertIn("lane=PRECHECK", result["href"])
        self.assertIn("terminal=t1", result["href"])
        self.assertIn("checkpoint=jfk-t1", result["href"])

    def test_stale_reading_is_not_current_after_page_ages(self):
        result = self.run_selection(query="?terminal=t1", minutes_old=20)
        self.assertIn("No fresh reading", result["summary"])
        self.assertNotIn("checkpoint=", result["href"])
        self.assertNotIn("Fastest", result["message"])


if __name__ == "__main__":
    unittest.main()
