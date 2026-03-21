"""Tests for the custom file provider."""

import json
import tempfile
from pathlib import Path

import pytest

from kg_enrichment.providers.custom_file import CustomFileProvider


@pytest.fixture
def provider():
    return CustomFileProvider()


class TestCustomFileProvider:
    @pytest.mark.asyncio
    async def test_ingest_csv(self, provider):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("name,type,value\n")
            f.write("Apple,organization,tech\n")
            f.write("Google,organization,tech\n")
            path = f.name

        result = await provider.ingest_file(path)
        assert len(result.raw_data) == 2
        assert result.raw_data[0]["name"] == "Apple"
        Path(path).unlink()

    @pytest.mark.asyncio
    async def test_ingest_json(self, provider):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"name": "Test", "value": 42}], f)
            path = f.name

        result = await provider.ingest_file(path)
        assert len(result.raw_data) == 1
        assert result.raw_data[0]["name"] == "Test"
        Path(path).unlink()

    @pytest.mark.asyncio
    async def test_ingest_jsonl(self, provider):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"name": "A"}\n')
            f.write('{"name": "B"}\n')
            path = f.name

        result = await provider.ingest_file(path)
        assert len(result.raw_data) == 2
        Path(path).unlink()

    @pytest.mark.asyncio
    async def test_ingest_text(self, provider):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Apple Inc. is a technology company based in Cupertino.")
            path = f.name

        result = await provider.ingest_file(path)
        assert len(result.raw_data) == 1
        assert "Apple" in result.raw_data[0]["text"]
        Path(path).unlink()

    @pytest.mark.asyncio
    async def test_ingest_nonexistent(self, provider):
        result = await provider.ingest_file("/nonexistent/file.csv")
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_metadata(self, provider):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("a,b\n1,2\n")
            path = f.name

        result = await provider.ingest_file(path)
        assert result.metadata["file_type"] == "csv"
        assert result.metadata["records"] == 1
        Path(path).unlink()
