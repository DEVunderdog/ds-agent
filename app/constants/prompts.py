CONTEXT_COLLECTION_INPUT_PROMPT = """
Note: Currently we don't handle missing values and unsupervised models.

To help me build the best model and analysis for you, please provide context on follwoing questions please.

1. Business Objective
- What decision or outcome are you trying to enable ?
- Is this primarily for: Prediction | Classification

2. Target variables
- What are you trying to predict? (column name)
- Is it: Binary | Continous/Regression

3. Dataset Domain & context
- What domain does this data come from?
(e.g. healthcare, finance, e-commerce, IoT sensors)
- Unit of observation? (e.g. one row = one customer, one transaction, one patient visit)

4. Column Semantics & Types
Note: Please list them exactly as they are in dataset
- Identifier columns (IDs, keys)
- Time/date columns then please
- Known categorical features
- Known numerical features
- Text/unstructured columns

5. Known relationships and constraints
- Any known interactions between features? (e.g., "price * quantity = revenue")
- Hierarchical relationships? (e.g., "city → state → country")
- Temporal dependencies? (e.g., "use past 7 days to predict next day")
- Domain-specific constraints? (e.g., "age must be 0-120", "percentages sum to 100")
"""

CONTEXT_COLLECTION_SYSTEM_PROMPT = """

"""