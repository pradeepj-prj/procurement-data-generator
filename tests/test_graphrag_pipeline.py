"""Tests for the content filtering and data masking pipeline."""

import pytest
from graphrag.llm.genai_hub import PipelineDetails, mask_nric


class TestNRICMasking:
    """Test the Singapore NRIC/FIN regex masking."""

    def test_citizen_pre_2000(self):
        text, entities = mask_nric("My NRIC is S1234567D")
        assert text == "My NRIC is MASKED_NRIC"
        assert "NRIC" in entities

    def test_citizen_post_2000(self):
        text, entities = mask_nric("ID: T0012345J")
        assert "MASKED_NRIC" in text
        assert "NRIC" in entities

    def test_foreigner_f(self):
        text, entities = mask_nric("FIN F9876543K")
        assert "MASKED_NRIC" in text

    def test_foreigner_g(self):
        text, entities = mask_nric("FIN G1234567X")
        assert "MASKED_NRIC" in text

    def test_foreigner_m(self):
        text, entities = mask_nric("ID M1234567A")
        assert "MASKED_NRIC" in text

    def test_case_insensitive(self):
        text, entities = mask_nric("nric s1234567d here")
        assert "MASKED_NRIC" in text
        assert "NRIC" in entities

    def test_multiple_nrics(self):
        text, entities = mask_nric("S1234567D and T9876543K")
        assert text.count("MASKED_NRIC") == 2
        assert entities == ["NRIC"]  # entity type listed once

    def test_no_nric(self):
        text, entities = mask_nric("Tell me about VND-HOKUYO")
        assert text == "Tell me about VND-HOKUYO"
        assert entities == []

    def test_partial_match_ignored(self):
        # Too few digits
        text, entities = mask_nric("S123456D")
        assert entities == []
        # Too many digits
        text, entities = mask_nric("S12345678D")
        assert entities == []

    def test_invalid_prefix_ignored(self):
        text, entities = mask_nric("X1234567D")
        assert entities == []

    def test_embedded_in_sentence(self):
        text, entities = mask_nric(
            "The employee with NRIC S9876543A submitted an invoice"
        )
        assert "MASKED_NRIC" in text
        assert "S9876543A" not in text


class TestPipelineDetails:
    def test_default_values(self):
        details = PipelineDetails()
        assert details.original_query == ""
        assert details.masked_query == ""
        assert details.entities_masked == []
        assert details.client_side_masked is False
        assert details.blocked is False
        assert details.blocked_by is None

    def test_to_dict(self):
        details = PipelineDetails(
            original_query="My NRIC is S1234567D",
            masked_query="My NRIC is MASKED_NRIC",
            entities_masked=["NRIC"],
            client_side_masked=True,
        )
        d = details.to_dict()
        assert d["data_masking"]["original_query"] == "My NRIC is S1234567D"
        assert d["data_masking"]["masked_query"] == "My NRIC is MASKED_NRIC"
        assert d["data_masking"]["entities_masked"] == ["NRIC"]
        assert d["data_masking"]["client_side_masked"] is True
        assert d["content_filtering"]["blocked"] is False

    def test_blocked_to_dict(self):
        details = PipelineDetails(blocked=True, blocked_by="content_filtering")
        d = details.to_dict()
        assert d["content_filtering"]["blocked"] is True
        assert d["content_filtering"]["blocked_by"] == "content_filtering"


class TestTracingLLMProxyPipeline:
    """Test that TracingLLMProxy captures pipeline details when available."""

    def test_without_pipeline(self):
        """Mock LLMs without chat_with_pipeline still work."""
        from graphrag.observability.trace import TracingLLMProxy, Span, _now_ms

        class MockLLM:
            model_name = "mock"

            def chat(self, messages):
                return "ok"

        span = Span(name="generate", start_ms=_now_ms())
        proxy = TracingLLMProxy(MockLLM())
        result = proxy.chat([{"role": "user", "content": "hi"}], span=span)

        assert result == "ok"
        assert proxy.pipeline_details == {}  # no pipeline method

    def test_with_pipeline(self):
        """LLMs with chat_with_pipeline get pipeline details captured."""
        from graphrag.observability.trace import TracingLLMProxy, Span, _now_ms

        class MockLLMWithPipeline:
            model_name = "mock"

            def chat_with_pipeline(self, messages):
                details = PipelineDetails(
                    original_query="test S1234567D",
                    masked_query="test MASKED_NRIC",
                    entities_masked=["NRIC"],
                    client_side_masked=True,
                )
                return "answer", details

        span = Span(name="generate", start_ms=_now_ms())
        proxy = TracingLLMProxy(MockLLMWithPipeline())
        result = proxy.chat([{"role": "user", "content": "test"}], span=span)

        assert result == "answer"
        assert proxy.pipeline_details["data_masking"]["entities_masked"] == ["NRIC"]
        assert proxy.pipeline_details["data_masking"]["client_side_masked"] is True


class TestQueryTracePipeline:
    """Test that QueryTrace includes pipeline field."""

    def test_pipeline_in_trace(self):
        from graphrag.observability.trace import QueryTrace

        trace = QueryTrace(question="test")
        trace.pipeline = {
            "data_masking": {"entities_masked": ["NRIC"]},
            "content_filtering": {"blocked": False},
        }
        d = trace.to_dict()
        assert "pipeline" in d
        assert d["pipeline"]["data_masking"]["entities_masked"] == ["NRIC"]

    def test_empty_pipeline(self):
        from graphrag.observability.trace import QueryTrace

        trace = QueryTrace(question="test")
        d = trace.to_dict()
        assert d["pipeline"] == {}
