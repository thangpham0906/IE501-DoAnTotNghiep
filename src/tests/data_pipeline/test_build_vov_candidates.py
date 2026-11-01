import unittest

from src.data_pipeline.build_vov_candidates import build_candidate, language_scores, normalize_text


class CandidateTests(unittest.TestCase):
    def test_normalize_text(self) -> None:
        self.assertEqual(normalize_text("  Pỉ   noọng\nđảy  "), "Pỉ noọng đảy")

    def test_language_scores(self) -> None:
        vi, tay = language_scores("Những người trong bản đã được Nhà nước hỗ trợ")
        self.assertGreater(vi, tay)
        vi, tay = language_scores("Pỉ noọng đảy slon lai món đây, bấu pền lừ")
        self.assertGreater(tay, vi)

    def test_build_candidate_keeps_warning_flags(self) -> None:
        row = {
            "source_url": "https://vov4.vov.vn/taynung/example-1.vov4",
            "summary_taynung_candidate": "Pỉ noọng đảy slon lai món đây, bấu pền lừ chang bản nẳm.",
            "body_blocks": [
                "Những người trong bản đã được Nhà nước hỗ trợ để phát triển đời sống và sản xuất.",
            ],
        }
        result = build_candidate(row)
        self.assertIsNotNone(result)
        self.assertIn("not_sentence_aligned", result["quality_flags"])
        self.assertIn("permission_not_confirmed", result["quality_flags"])


if __name__ == "__main__":
    unittest.main()
