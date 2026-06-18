# asi

Minimal, dependency-free Python app managed with [uv](https://docs.astral.sh/uv/).

## Why Python 3.13

3.13 is the newest Python supported by the full ML/AI stack we may add later
(numpy, scipy, scikit-learn, torch, jax, **tensorflow**, hugging face,
langchain, pydantic, pytest). TensorFlow is the limiting factor: its latest
stable release supports up to 3.13 and does not yet support 3.14.

## Usage

```bash
uv run main.py
```
