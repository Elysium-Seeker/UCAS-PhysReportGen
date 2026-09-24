"""Behavioral checks for the skill CLI, calculation helpers and build freshness."""
import base64
import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
SCRIPTS=REPO/"skills"/"ucas-physics-report"/"scripts"
sys.path.insert(0,str(SCRIPTS))
import report
import build
from reportlib import read_json,write_json,sha256,validate_data,validate_results
from physics import linear_fit,mean_uncertainty,propagate,angular_difference,save_results


class Workflow(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="ucas-skill-test-")
        self.root=Path(self.temp.name).resolve()
        self.assertTrue(self.root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.addCleanup(self.temp.cleanup)
        self.photo=self.root/"照片.png"
        self.photo.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1cAAAAASUVORK5CYII="))
        self.project=self.root/"报告 with spaces"
        self.config_patch=patch.object(report,"CONFIG",self.root/"config.json")
        self.config_patch.start(); self.addCleanup(self.config_patch.stop)

    def project_ready(self):
        args=SimpleNamespace(experiment="硅光电池",output=str(self.project),
                             records=[str(self.photo)],preview=None,observations=None,library=None)
        with redirect_stdout(StringIO()): report.init_project(args)
        data=read_json(self.project/"data.json")
        data["metadata"]={"student_name":"测试_样例&","student_id":"001","group":"1-01","seat":"1",
                          "date":"2026-09-24","teacher":"测试教师","room":"测试室"}
        data["requirements"]["preview_required"]=False
        data["tables"]=[{"id":"raw","title":"Test readings","columns":[{"key":"x","label":"X","unit":"V"},
                                                                       {"key":"y","label":"Y","unit":"mA"}],
                        "rows":[{"values":{"x":x,"y":2*x+1},
                                 "source":{"image":"photos/photo-001.png","table":"1","row":str(x+1)}}
                                for x in range(3)]}]
        write_json(self.project/"data.json",data)
        (self.project/"analyze.py").write_text("# test-only fixture\n",encoding="utf-8")
        (self.project/"content.tex").write_text(
            "\\section{测试}\n\\input{generated/tables/raw.tex}\n斜率 $\\Result{slope}$。\n",encoding="utf-8")
        save_results(self.project,quantities=[{"id":"slope","value":2.0,"unit":"mA/V",
                                               "method":"OLS test","inputs":["table:raw"]}])
        return data

    def test_all_experiments_resolve_by_name_and_alias(self):
        entries=report.catalog()
        self.assertEqual(len(entries),14)
        for e in entries:
            with self.subTest(e=e["id"]):
                for name in [e["title"],e["id"],e["number"]]+e["aliases"]:
                    self.assertEqual(report.resolve(name)["id"],e["id"])
                self.assertTrue((SCRIPTS.parent/e["recipe"]).is_file())
        self.assertEqual(report.resolve("请帮我生成RLC实验报告")["id"],"rlc")
        with self.assertRaises(ValueError): report.resolve("光")
        with self.assertRaises(ValueError): report.resolve("不存在的实验")
        with self.assertRaises(ValueError): report.resolve("")

    def test_init_copies_original_bytes_and_refuses_overwrite(self):
        self.project_ready()
        self.assertEqual(sha256(self.photo),sha256(self.project/"photos/photo-001.png"))
        args=SimpleNamespace(experiment="硅光电池",output=str(self.project),
                             records=[str(self.photo)],preview=None,observations=None,library=None)
        with self.assertRaises(ValueError): report.init_project(args)
        self.assertTrue(self.photo.is_file())

    def test_changed_source_is_rejected(self):
        self.project_ready()
        self.assertTrue(validate_data(self.project)["valid"])
        (self.project/"photos/photo-001.png").write_bytes(b"changed")
        self.assertFalse(validate_data(self.project)["valid"])

    def test_unreadable_value_and_unresolved_issue_are_not_accepted(self):
        data=self.project_ready()
        data["tables"][0]["rows"][0]["values"]["x"]=None
        data["issues"]=[{"id":"r1","status":"unresolved","description":"unreadable first cell"}]
        write_json(self.project/"data.json",data)
        self.assertFalse(validate_data(self.project)["valid"])
        with self.assertRaises(ValueError): save_results(self.project)

    def test_sources_units_and_dates_required(self):
        data=self.project_ready()
        del data["tables"][0]["rows"][1]["source"]
        del data["tables"][0]["columns"][0]["unit"]
        data["metadata"]["date"]="2026-02-30"
        write_json(self.project/"data.json",data)
        self.assertGreaterEqual(len(validate_data(self.project)["errors"]),3)

    def test_partial_data_remains_visible_and_never_complete(self):
        data=self.project_ready()
        data["tables"][0]["rows"][1]["values"]["y"]=None
        data["issues"]=[{"id":"r2","status":"unresolved","description":"crossed-out y"}]
        write_json(self.project/"data.json",data)
        self.assertFalse(validate_data(self.project)["valid"])
        self.assertTrue(validate_data(self.project,allow_incomplete=True)["valid"])
        with self.assertRaises(ValueError): save_results(self.project,allow_incomplete=True)
        save_results(self.project,allow_incomplete=True,notes=["Row 2 y unavailable; no slope inferred"])
        (self.project/"content.tex").write_text(r"\input{generated/tables/raw.tex}",encoding="utf-8")
        check=build.render(self.project)
        self.assertTrue(check["warnings"])
        self.assertIn(r"\textemdash{}",(self.project/"generated/tables/raw.tex").read_text())
        self.assertFalse(build.status(self.project)["complete"])

    def test_qualitative_experiment_can_use_actual_observation_photo(self):
        data=self.project_ready()
        data["tables"]=[]
        data["observations"]=[{"id":"pattern","text":"Test image observation",
                               "source":{"image":"photos/photo-001.png"}}]
        write_json(self.project/"data.json",data)
        save_results(self.project,figures=[{"id":"pattern","path":"photos/photo-001.png",
                                            "caption":"Actual supplied observation",
                                            "observation_ids":["pattern"]}])
        (self.project/"content.tex").write_text(r"\input{generated/figures/pattern.tex}",encoding="utf-8")
        self.assertTrue(build.render(self.project)["valid"])

    def test_missing_metadata_is_explicit_draft(self):
        data=self.project_ready()
        data["metadata"]={}
        data["requirements"]["preview_required"]=True
        write_json(self.project/"data.json",data)
        save_results(self.project,quantities=[{"id":"slope","value":2,"unit":"mA/V",
                                              "method":"OLS","inputs":["table:raw"]}])
        check=build.render(self.project)
        self.assertTrue(check["valid"])
        self.assertIn("Missing required preview-report photo",check["warnings"])
        self.assertIn("待补充",(self.project/"report.tex").read_text(encoding="utf-8"))

    def test_stale_results_rejected_after_data_or_script_changes(self):
        data=self.project_ready()
        self.assertTrue(validate_results(self.project)["valid"])
        data["tables"][0]["rows"][1]["values"]["y"]=9
        write_json(self.project/"data.json",data)
        self.assertFalse(validate_results(self.project)["valid"])
        save_results(self.project)
        (self.project/"analyze.py").write_text("# modified calculation\n",encoding="utf-8")
        self.assertFalse(validate_results(self.project)["valid"])

    def test_stale_figures_and_unknown_table_links_rejected(self):
        self.project_ready()
        fig=self.project/"figures"/"a.png"; fig.write_bytes(self.photo.read_bytes())
        save_results(self.project,figures=[{"id":"graph","path":"figures/a.png",
                                            "caption":"fixture","table_ids":["raw"]}])
        fig.write_bytes(b"changed")
        self.assertFalse(validate_results(self.project)["valid"])
        with self.assertRaises(ValueError):
            save_results(self.project,figures=[{"id":"graph","path":"figures/a.png",
                                                "caption":"fixture","table_ids":["unknown"]}])

    def test_changed_numerical_helper_invalidates_results(self):
        self.project_ready()
        with (self.project/"physics.py").open("a",encoding="utf-8") as stream:
            stream.write("\n# changed numerical helper\n")
        self.assertFalse(validate_results(self.project)["valid"])

    def test_renderer_keeps_data_linkage_and_escapes_header(self):
        self.project_ready(); build.render(self.project)
        tex=(self.project/"report.tex").read_text(encoding="utf-8")
        self.assertIn(r"测试\_样例\&",tex)
        self.assertIn(r"\includegraphics",(self.project/"generated/appendix.tex").read_text())
        content=self.project/"content.tex"
        content.write_text(r"\input{generated/tables/raw.tex}\Result{doesnotexist}",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"Undefined result"): build.render(self.project)
        content.write_text(r"\input{generated/tables/raw.tex}\input{generated/tables/old.tex}",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"stale generated"): build.render(self.project)
        content.write_text(r"\section{omitted table}",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"must include table"): build.render(self.project)

    def test_failed_compile_never_reuses_existing_pdf(self):
        self.project_ready()
        old=self.project/"report.pdf"; old.write_bytes(b"old pdf that must not count")
        write_json(self.project/"build.json",{"compiled":True})
        with patch.object(build.shutil,"which",return_value="fake-xelatex"), \
             patch.object(build.subprocess,"run",return_value=subprocess.CompletedProcess([],1,"failed","error")):
            with self.assertRaisesRegex(ValueError,"failed"): build.compile_report(self.project)
        self.assertEqual(old.read_bytes(),b"old pdf that must not count")
        self.assertFalse(build.current_build(self.project))
        self.assertFalse(read_json(self.project/"build.json")["compiled"])

    def test_source_edits_invalidate_build_and_visual_review(self):
        self.project_ready()
        def fake_latex(command,**kwargs):
            dest=Path(next(x.split("=",1)[1] for x in command if x.startswith("-output-directory=")))
            from pypdf import PdfWriter
            writer=PdfWriter(); writer.add_blank_page(width=595,height=842)
            writer.write(dest/"report.pdf")
            (dest/"report.log").write_text("clean",encoding="utf-8")
            return subprocess.CompletedProcess(command,0,"ok","")
        with patch.object(build.shutil,"which",return_value="fake-xelatex"), \
             patch.object(build.subprocess,"run",side_effect=fake_latex):
            build.compile_report(self.project)
        self.assertTrue(build.current_build(self.project))
        preview=build.preview(self.project)
        self.assertEqual(len(preview["pages"]),1)
        with self.assertRaises(ValueError): build.record_review(self.project,[],"no pages")
        build.record_review(self.project,[1],"Synthetic test page reviewed by test contract")
        self.assertTrue(build.status(self.project)["complete"])
        with (self.project/"content.tex").open("a",encoding="utf-8") as f: f.write("\nChanged prose")
        self.assertFalse(build.status(self.project)["complete"])

    def test_path_escape_in_results_rejected(self):
        self.project_ready()
        with self.assertRaises(ValueError):
            save_results(self.project,figures=[{"id":"bad","path":"../照片.png",
                                               "caption":"bad","table_ids":["raw"]}])

    def test_numeric_helpers_known_solutions_and_correlations(self):
        fit=linear_fit([0,1,2,3],[1,3,5,7])
        self.assertAlmostEqual(fit["slope"],2)
        self.assertAlmostEqual(fit["intercept"],1)
        self.assertAlmostEqual(fit["r_squared"],1)
        self.assertAlmostEqual(fit["slope_stderr"],0)
        with self.assertRaises(ValueError): linear_fit([1,1,1],[2,3,4])
        with self.assertRaises(ValueError): linear_fit([0,1],[0,1])
        u=mean_uncertainty([1,2,3],instrument_limit=0.3)
        self.assertAlmostEqual(u["u_a"],1/(3**0.5))
        self.assertAlmostEqual(u["u_b"],0.3/(3**0.5))
        self.assertIsNone(mean_uncertainty([1])["u_a"])
        self.assertIsNone(mean_uncertainty([1,2,3])["u_c"])
        self.assertAlmostEqual(propagate([1,-1],[[1,1],[1,1]]),0)
        self.assertAlmostEqual(propagate([1,1],[[1,1],[1,1]]),2)
        with self.assertRaises(ValueError): propagate([1,1],[[1,2],[2,1]])
        self.assertEqual(angular_difference(1,359),2)
        self.assertEqual(angular_difference(359,1),-2)

    def test_install_backup_and_reproducible_skill_only_package(self):
        target=self.root/"codex-home"
        command=[sys.executable,"-X","utf8",str(REPO/"scripts/install_skill.py"),"--codex-home",str(target)]
        first=subprocess.run(command,capture_output=True,text=True,encoding="utf-8",check=True)
        installed=Path(json.loads(first.stdout)["installed"])
        self.assertEqual((installed/"SKILL.md").read_bytes(),(SCRIPTS.parent/"SKILL.md").read_bytes())
        (installed/"user-note.txt").write_text("preserve me",encoding="utf-8")
        second=subprocess.run(command,capture_output=True,text=True,encoding="utf-8",check=True)
        backup=Path(json.loads(second.stdout)["backup"])
        self.assertEqual((backup/"user-note.txt").read_text(),"preserve me")
        archive=self.root/"skill.zip"
        cmd=[sys.executable,str(REPO/"scripts/package_skill.py"),"--output",str(archive)]
        subprocess.run(cmd,capture_output=True,check=True)
        digest=sha256(archive)
        subprocess.run(cmd,capture_output=True,check=True)
        self.assertEqual(digest,sha256(archive))
        with zipfile.ZipFile(archive) as z:
            self.assertIn("ucas-physics-report/SKILL.md",z.namelist())
            self.assertTrue(all(n.startswith("ucas-physics-report/") for n in z.namelist()))
            self.assertFalse(any("__pycache__" in n or n.endswith("config.json") for n in z.namelist()))


if __name__=="__main__":
    unittest.main()
