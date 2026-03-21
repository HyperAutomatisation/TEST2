# Thesis Document Analyzer

A Python tool for analyzing academic thesis documents. It extracts structure, sections, citations, keywords, and generates summary reports.

## Features

- **Document Parsing**: Extract text from PDF and plain-text thesis documents
- **Structure Analysis**: Identify chapters, sections, subsections, and their hierarchy
- **Citation Extraction**: Detect and parse in-text citations and reference lists
- **Keyword Extraction**: Identify key terms and compute term frequency
- **Readability Metrics**: Compute word count, sentence count, and readability scores
- **Summary Report**: Generate a structured JSON or text report of the analysis

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Command Line

```bash
# Analyze a thesis document
python -m thesis_analyzer analyze path/to/thesis.pdf

# Analyze a plain text file
python -m thesis_analyzer analyze path/to/thesis.txt

# Generate a JSON report
python -m thesis_analyzer analyze path/to/thesis.pdf --format json --output report.json

# Generate a text report
python -m thesis_analyzer analyze path/to/thesis.pdf --format text
```

### Python API

```python
from thesis_analyzer import ThesisAnalyzer

analyzer = ThesisAnalyzer()
result = analyzer.analyze("path/to/thesis.pdf")

print(result.title)
print(result.sections)
print(result.citations)
print(result.keywords)
print(result.summary())
```

## Project Structure

```
thesis_analyzer/
├── __init__.py          # Package exports
├── __main__.py          # CLI entry point
├── parser.py            # Document text extraction
├── analyzer.py          # Structure and content analysis
├── citations.py         # Citation detection and parsing
├── keywords.py          # Keyword extraction
├── report.py            # Report generation
└── models.py            # Data models
tests/
├── test_parser.py
├── test_analyzer.py
└── test_citations.py
```

## License

MIT
