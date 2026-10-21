"""Exercise the redesigned discovery flow and shared navigation offline."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def inline_scripts(html):
    return [source for attrs, source in re.findall(r'<script\b([^>]*)>(.*?)</script>', html, re.S)
            if 'src=' not in attrs and 'application/' not in attrs]


class SharedFlowRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='tsa-site-flow-')
        spec = importlib.util.spec_from_file_location('tsa_site_flow_app', ROOT / 'app.py')
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        with patch.dict(os.environ, {'DB_PATH':str(Path(cls.temp.name) / 'test.db'),
                'ENABLE_POLLER':'false','SUPABASE_URL':'','SUPABASE_SERVICE_ROLE_KEY':'',
                'ENABLE_ANALYTICS':'false','ENABLE_ADSENSE':'false'}):
            spec.loader.exec_module(cls.module)
        cls.module.app.config['TESTING'] = True
        cls.module.get_lite_brain_insights = lambda: []
        cls.module.collect_once = lambda: {'ok':[], 'errors':[]}
        cls.module.supabase_history_rows = lambda *args, **kwargs: None
        cls.module.supabase_historical_24h_average = lambda *args, **kwargs: None
        cls.module.supabase_checkpoint_24h_average = lambda *args, **kwargs: None
        cls.module.init_db()
        cls.module._db_initialized = True
        cls.client = cls.module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        sys.modules.pop('tsa_site_flow_app', None)

    def html(self, route):
        response = self.client.get(route)
        self.assertEqual(response.status_code, 200, route)
        return response.get_data(as_text=True)

    def test_search_results_precede_board_and_optional_map(self):
        html = self.html('/')
        self.assertLess(html.index('id="q"'), html.index('id="hero-search-results"'))
        self.assertLess(html.index('id="hero-search-results"'), html.index('id="board"'))
        self.assertLess(html.index('id="board"'), html.index('id="airport-map"'))
        self.assertRegex(html, r'<details class="flow-map-details">')
        self.assertIn('data-clear-search', html)

    def test_directory_answer_precedes_optional_chart(self):
        html = self.html('/airports')
        self.assertLess(html.index('id="board"'), html.index('id="netcompare"'))
        self.assertIn('id="reset-directory"', html)
        self.assertIn('id="directory-search-status" role="status"', html)

    def test_core_routes_share_primary_navigation_and_skip_target(self):
        expected = ['/airports','/when-should-i-leave','/guide/tsa-wait-times','/methodology']
        routes = ['/', '/airports', '/when-should-i-leave','/methodology','/about','/privacy','/contact',
                  '/best-time-to-get-to-the-airport','/guide/tsa-wait-times',self.module.airport_seo_slug('JFK')]
        for route in routes:
            with self.subTest(route=route):
                html = self.html(route)
                navs = re.findall(r'<nav\b[^>]*aria-label="Primary navigation"[^>]*>(.*?)</nav>', html, re.S)
                self.assertEqual(len(navs), 1)
                self.assertEqual(re.findall(r'<a\b[^>]*href="([^"]+)"',navs[0]), expected)
                self.assertEqual(html.count('id="main-content"'), 1)
                self.assertIn('href="#main-content"', html)
                self.assertLessEqual(navs[0].count('aria-current="page"'), 1)

    @unittest.skipUnless(shutil.which('node'), 'Node checks browser JavaScript syntax')
    def test_rendered_inline_scripts_compile(self):
        scripts=[]
        for route in ['/', '/airports', self.module.airport_seo_slug('JFK'), '/when-should-i-leave']:
            scripts.extend(inline_scripts(self.html(route)))
        result=subprocess.run(['node','-e','JSON.parse(require("fs").readFileSync(0,"utf8")).forEach(s=>new Function(s));'],
                              input=json.dumps(scripts), text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)


@unittest.skipUnless(shutil.which('node'), 'Node executes the browser interactions')
class DiscoveryBehaviorTests(unittest.TestCase):
    def run_node(self, source):
        result=subprocess.run(['node','-e',source], cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_home_search_exact_match_and_recovery(self):
        script=next(s for s in inline_scripts((ROOT/'templates/home.html').read_text()) if 'var heroResults=' in s)
        result=self.run_node('''
const vm=require('vm');
function el(extra={}) {return Object.assign({style:{},hidden:true,dataset:{},events:{},textContent:'',attrs:{},addEventListener(k,v){this.events[k]=v;},focus(){this.focused=true;},setAttribute(k,v){this.attrs[k]=v;},classList:{remove(){},add(){}}},extra);}
const q=el({value:''}), clear=el(), status=el(), empty=el();
const rows=[el({dataset:{code:'JFK',city:'new york john f kennedy',wait:30}}),el({dataset:{code:'LGA',city:'new york laguardia',wait:5}})];
const heroRows=rows.map(r=>el({href:'/airports/'+r.dataset.code.toLowerCase()+'-tsa-wait-times',dataset:{code:r.dataset.code.toLowerCase(),search:r.dataset.code.toLowerCase()+' '+r.dataset.city}}));
const board=el({querySelectorAll:()=>rows});
const hero=el({querySelectorAll:()=>heroRows,querySelector:s=>s==='[data-search-status]'?status:empty});
const document={getElementById:id=>({q,board,'hero-search-results':hero}[id]),querySelectorAll:s=>s==='[data-clear-search]'?[clear]:[]};
let destination='';
vm.runInNewContext(%s,{document,window:{location:{assign:href=>destination=href}}});
q.value='jfk';q.events.input();q.events.keydown({key:'Enter'});
const exact={shown:heroRows.filter(r=>!r.hidden).length,status:status.textContent,destination};
q.value='no-such-airport';q.events.input();const missing={empty:!empty.hidden,rows:rows.filter(r=>r.style.display!=='none').length};
clear.events.click();
process.stdout.write(JSON.stringify({exact,missing,recovered:q.value===''&&hero.hidden&&q.focused&&rows.every(r=>r.style.display==='')}));
''' % json.dumps(script))
        self.assertEqual(result['exact']['shown'],1)
        self.assertEqual(result['exact']['status'],'1 result')
        self.assertTrue(result['exact']['destination'].endswith('jfk-tsa-wait-times'))
        self.assertTrue(result['missing']['empty'])
        self.assertEqual(result['missing']['rows'],0)
        self.assertTrue(result['recovered'])

    def test_directory_reset_recovers_search_and_region(self):
        script=next(s for s in inline_scripts((ROOT/'templates/airports.html').read_text()) if 'var cards=' in s)
        result=self.run_node('''
const vm=require('vm');
function el(extra={}){return Object.assign({dataset:{},style:{},events:{},attrs:{},textContent:'',classList:{add(){},remove(){},toggle(){}},addEventListener(k,v){this.events[k]=v;},setAttribute(k,v){this.attrs[k]=v;},focus(){this.focused=true;},querySelector:()=>null},extra);}
const q=el({value:''}),status=el(),empty=el(),reset=el();
const cards=[el({dataset:{code:'JFK',city:'new york',region:'NE'}}),el({dataset:{code:'LAX',city:'los angeles',region:'W'}})];
const chips=[el({dataset:{region:'all'}}),el({dataset:{region:'W'}})];
const document={getElementById:id=>({q,board:el({querySelectorAll:()=>cards}),'directory-search-status':status,'directory-empty':empty,'reset-directory':reset}[id]),querySelectorAll:()=>chips};
vm.runInNewContext(%s,{document,fetch:async()=>({json:async()=>({airports:[]})})});
chips[1].events.click();q.value='JFK';q.events.input();
const missing=!empty.hidden&&cards.every(c=>c.style.display==='none');
reset.events.click();
process.stdout.write(JSON.stringify({missing,recovered:cards.every(c=>c.style.display==='')&&q.value===''&&q.focused,status:status.textContent,allPressed:chips[0].attrs['aria-pressed']}));
''' % json.dumps(script))
        self.assertTrue(result['missing'])
        self.assertTrue(result['recovered'])
        self.assertEqual(result['status'],'2 airports shown')
        self.assertEqual(result['allPressed'],'true')

    def render_network(self,payload):
        script=next(s for s in inline_scripts((ROOT/'templates/airports.html').read_text()) if 'var PALETTE=' in s)
        return self.run_node('''
const vm=require('vm');
function el(extra={}) {return Object.assign({style:{},dataset:{},innerHTML:'',textContent:'',value:'9',addEventListener(){},setAttribute(){},classList:{remove(){},add(){}}},extra);}
const readings=el(), empty=el();
const mount=el({dataset:{days:'30'},querySelector:s=>s==='.nc-reading-list'?readings:el(),querySelectorAll:()=>[]});
vm.runInNewContext(%s,{document:{getElementById:id=>id==='netcompare'?mount:empty},fetch:async()=>({json:async()=>(%s)})});
setImmediate(()=>process.stdout.write(JSON.stringify({html:mount.innerHTML,readings:readings.innerHTML,empty:empty.textContent})));
''' % (json.dumps(script),json.dumps(payload)))

    def test_network_missing_hour_stays_unknown_in_accessible_readout(self):
        result=self.render_network({'airports':[{'code':'JFK','rows':[{'hour':0,'avg_wait':0,'samples':2},{'hour':2,'avg_wait':30,'samples':3}]}]})
        self.assertIn('Unavailable',result['readings'])
        self.assertNotIn('0 min',result['readings'])
        self.assertRegex(result['html'],r'class="nc-line"[^>]*d="M[^"L]*M[^"L]*"')

    def test_network_no_history_has_recovery_message(self):
        result=self.render_network({'airports':[]})
        self.assertEqual(result['html'],'')
        self.assertIn('Not enough recent history',result['empty'])


if __name__=='__main__':
    unittest.main()
