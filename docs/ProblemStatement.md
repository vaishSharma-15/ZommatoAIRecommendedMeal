## Problem Statement: AI‑Powered Restaurant Recommendation System (Zomato‑Style)

Build an AI-powered restaurant recommendation service inspired by Zomato. The system must combine **structured restaurant data** with a **Large Language Model (LLM)** to generate **personalized, human-readable recommendations** based on a user’s preferences.

## Objective

Design and implement an application that:

- Accepts user preferences (e.g., location, budget, cuisine, minimum rating, and other constraints)
- Uses a real-world restaurant dataset
- Produces a ranked shortlist of restaurants with clear explanations for each recommendation
- Presents results in a user-friendly format (CLI or UI is acceptable unless otherwise specified)

## Data Source

Use the Zomato restaurant dataset from Hugging Face:

- Dataset: `ManikaSaini/zomato-restaurant-recommendation`
- Link: `https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation`

## Core Workflow

### 1) Data ingestion & preprocessing

- Load the dataset.
- Clean and normalize relevant fields (e.g., handle missing values, unify location/cuisine strings).
- Extract the minimum set of fields needed for recommendations, such as:
  - Restaurant name
  - Location / city / area
  - Cuisine(s)
  - Cost / price for two (or equivalent)
  - Rating (and vote count if available)

### 2) User preference collection

Collect preferences including:

- **Location** (e.g., Delhi, Bangalore)
- **Budget** (e.g., low/medium/high or a numeric range)
- **Cuisine** (e.g., Italian, Chinese)
- **Minimum rating**
- **Optional constraints** (e.g., family-friendly, quick service, outdoor seating)

### 3) Retrieval / filtering layer

- Filter candidate restaurants using the structured criteria (location, cuisine, budget, rating).
- If too many candidates remain, reduce the list (e.g., top-N by rating/votes or diversity sampling) before calling the LLM.
- Prepare a compact, structured representation of candidates to feed into the LLM prompt.

### 4) LLM recommendation & explanation

Use the LLM to:

- Rank the candidate restaurants for the specific user
- Provide brief explanations of why each option matches the preferences
- Optionally provide a short summary comparing the top choices

### 5) Output presentation

Display the top recommendations (e.g., top 3–10). Each recommendation should include:

- Restaurant name
- Location
- Cuisine(s)
- Rating
- Estimated cost
- AI-generated explanation (1–3 sentences)

## Expected Output (Acceptance Criteria)

The application is considered complete when it can:

- Ingest the dataset and build a usable restaurant index
- Accept user preferences and produce a **ranked** list of recommendations
- Provide **explanations grounded in the provided restaurant attributes**
- Handle common edge cases (e.g., no matches → relax constraints or explain why)
