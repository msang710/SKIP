import unittest

from scripts.workflow_report import WorkflowError, build_summary, render_brief, render_detail, validate_result


def result():
    return {"schema": "workflow-result/v1", "requested_outcome": "Local implementation", "outcome_status": "complete",
            "changes": ["prepare added"], "evidence": [{"surface": "test", "status": "PASS", "reference": "test.log"}],
            "authorization": {"status": "ALLOW", "reasons": []}, "gaps": [], "next_decision": None}


class ReportTests(unittest.TestCase):
    def test_all_nonpassing_states_survive_brief(self):
        for status in ("FAIL", "NOT_RUN", "STALE", "BLOCKED", "EVIDENCE_PENDING"):
            with self.subTest(status=status):
                value = result()
                value["evidence"].append({"surface": "gui", "status": status, "summary": "screen check"})
                self.assertIn(status, render_brief(value))
                self.assertEqual(validate_result(value)["outcome_status"], "partial")

    def test_missing_reference_cannot_be_pass(self):
        value = result()
        value["evidence"][0].pop("reference")
        self.assertIn("EVIDENCE_PENDING", render_brief(value))
        self.assertEqual(value["evidence"][0]["status"], "PASS")  # Caller data is not mutated.

    def test_authorization_is_not_completion(self):
        value = result()
        value["evidence"] = []
        summary = build_summary(value)
        self.assertEqual(summary["detail"]["outcome_status"], "partial")
        self.assertIn("EVIDENCE_PENDING", render_brief(value))
        with self.assertRaises(WorkflowError):
            validate_result({"schema": "workflow-plan/v1", "status": "prepared"})

    def test_readiness_and_authority_both_visible(self):
        value = result()
        value["document_readiness"] = "READY"
        value["authorization"] = {"status": "BLOCKED", "action": "deploy", "reasons": ["DEPLOY_APPROVAL_MISSING"]}
        text = render_brief(value)
        self.assertIn("READY", text)
        self.assertIn("BLOCKED", text)
        self.assertIn("DEPLOY_APPROVAL_MISSING", text)

    def test_detail_retains_manifest_and_provenance(self):
        value = result()
        value["selection"] = {"documents": ["prd.md"], "status": "ambiguous", "warnings": ["choose goal"]}
        value["authorization"]["basis"] = [{"event_id": "abc"}]
        self.assertIn("prd.md", render_detail(value))
        self.assertIn("abc", render_detail(value))
        self.assertIn("ambiguous", render_brief(value))

    def test_schema_validation(self):
        for field, bad in (("evidence", {}), ("changes", "x"), ("authorization", {}), ("next_decision", 1)):
            value = result()
            value[field] = bad
            with self.assertRaises(WorkflowError):
                validate_result(value)

    def test_normalization_is_idempotent(self):
        value = result()
        value["evidence"] = []
        normalized = validate_result(value)
        self.assertEqual(normalized, validate_result(normalized))


if __name__ == "__main__":
    unittest.main()
