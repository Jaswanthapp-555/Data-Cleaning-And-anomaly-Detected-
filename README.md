# CleanCore: Automated Data Quality & Anomaly Profiler

> Upload a dataset, see exactly what is wrong with it, fix it under your own control, and download a clean dataset together with a full audit report.

---

## 1. What is CleanCore?

Real-world data is messy. Values are missing, rows are duplicated, numbers are stored as text, and some values are so extreme that nobody is sure whether they are real or mistakes. Before any analysis or reporting can be trusted, someone has to find these problems, decide what to do about each one, and keep a record of what was changed.

**CleanCore** is a web application that does this work:

- it **automatically analyzes** a dataset (CSV or Excel) and shows every quality problem it finds;
- it lets the user **review and fix** each problem with full control, one decision at a time;
- it keeps a complete **Change History** of every modification;
- it calculates an explainable **Quality Score** before and after cleaning;
- it can **compare two versions** of a dataset (a Reference and a Current one) and report what changed;
- it generates professional **HTML and PDF reports** and a cleaned dataset for download.

The word *automated* in the name refers to automatic **analysis, detection, profiling and recommendations**. It never means automatic destructive cleaning. CleanCore does not delete, replace or convert anything unless the user chooses to.

## 2. Who is it for?

- Analysts and students who need to prepare a dataset before analysis.
- Teams that receive a new version of a dataset and want to know exactly what changed.
- Reviewers who need proof of what was changed in a dataset, and why.

## 3. Core principles

These rules shape every feature in the application.

1. **Analyze first, clean second.** Uploading a dataset never modifies it. The user first sees what is wrong, and only then chooses what to do.
2. **Nothing happens silently.** Deleting, filling, replacing, converting and removing duplicates all show a preview or confirmation first.
3. **The original data is never touched.** All edits happen on a *working copy*. "Reset to Original" restores the uploaded state at any time.
4. **Every change is recorded.** The Change History logs each action (what, where, old value, new value, method) and appears in the final reports.
5. **Statistics are used carefully.** An outlier is not automatically an error. Drift is only claimed when a statistical test supports it. Cautious wording ("potential", "possible") is used when evidence is limited.
6. **Everything is computed from the user's data.** No column names, scores, charts or recommendations are hard-coded.
7. **One source of truth.** Each dataset has one authoritative working copy, and every page, chart, score and report reads that same latest state.

## 4. Two modes

On the Home page the user chooses a mode.

### Single Dataset mode

```
Upload -> Automatic analysis -> Issue Center -> Visualize -> Clean
      -> Re-analyze -> Review the real cleaned data
      -> (make more changes, or) Finalize -> Report & downloads
```

### Compare Datasets mode

A **Reference** (the earlier or baseline version) and a **Current** (the newer version) dataset. Each is analyzed, cleaned and finalized on its own. The comparison answers the question: *what changed from Reference to Current?*

```
Reference:  Upload -> Analyze -> Clean -> Review -> Finalize
Current:    Upload -> Analyze -> Clean -> Review -> Finalize
                                  |
            Comparison dashboard -> Comparison report & downloads
```

A *Preview Comparison* is available as soon as both datasets are loaded (clearly labeled as based on unfinalized working copies). The *Final Comparison* is available once both datasets are finalized, and it is the version used in reports.

## 5. Tour of the application

| Page | What it does |
|---|---|
| **Home** | Choose Single Dataset or Compare Datasets. |
| **Upload Dataset** | Upload a CSV or Excel file (choose a worksheet for Excel), preview the data, then start the analysis. |
| **Dataset Overview** | Dataset Health Overview with the overall Quality Score, the score breakdown, key statistics, and a column-by-column summary. |
| **Issue Center** | Every detected issue grouped by category, with severity, affected counts, a recommendation, and **Show Affected Records** to inspect the exact rows. |
| **Visualization** | Automatic overview charts for the whole dataset, plus a custom chart builder and a gallery of saved charts. |
| **Cleaning** | The Cleaning Studio: all the actions that modify the working copy (see section 7). |
| **Change History** | The audit log of every change made to the working copy. |
| **Review & Finalize** | Inspect the actual current data, then finalize it or go back and make more changes. |
| **Reports & Downloads** | Download reports, the cleaned dataset and the missing-values audit log. |
| **Comparison Dashboard** *(Compare mode)* | Summary and detail of what changed between Reference and Current. |

The interface supports three themes: **Light**, **Dark** and **Dim**.

## 6. Data quality concepts

### 6.1 What CleanCore detects

| Category | Meaning | Example |
|---|---|---|
| **Missing values** | Empty cells. | A blank `age`. |
| **Duplicate rows** | Rows that are *exactly* identical in every column. | The same full record entered twice. |
| **Data-type issues** | A column stored in a form that does not match its content. | Numbers stored as text, or a whole-number column with a few decimal values. |
| **Suspicious values** | Values that look logically invalid or inconsistently formatted. | A negative quantity, or "pay pal" next to "PayPal". |
| **Potential outliers** | Values statistically far from the rest of the column (IQR-based). | One income of 400,000 among values around 60,000. |

### 6.2 Outliers vs. suspicious values

An **outlier** is *unusual*, but it can be perfectly valid, for example a genuinely large order. A **suspicious value** looks *wrong*, for example a negative age. This is why outliers are flagged as "potential" and are never changed automatically: the user decides to **keep**, **correct**, **replace** or **delete** each one.

### 6.3 Exact duplicates

Two rows are duplicates **only if every cell is identical**. If even one meaningful value differs, the rows are different records and are never removed automatically.

| name | age | city | |
|---|---|---|---|
| A | 20 | Chennai | |
| A | 20 | Chennai | duplicate of the row above |
| A | 21 | Chennai | **not** a duplicate (age differs) |

### 6.4 Data-type issues and conversions

| Conversion | Rule |
|---|---|
| Whole number to decimal | Always safe. |
| Decimal to whole number | Safe only if every value is already a whole number. Otherwise the user is warned how many values will be rounded and must confirm. |
| Number to text | Always possible, but the column loses numeric analysis (useful mainly for ID-like numbers such as zip codes). |
| Text to number | Only for values that really are numbers. Values that cannot be converted are listed so the user can decide what to do with them. |
| Text to date | Only for values in a recognizable date format. Failures are listed. |
| Date to text | Always possible. |

Every conversion shows a **preview** first (current type, proposed type, affected values, values that cannot convert) and needs the user's approval.

### 6.5 Handling missing values

The user chooses one of: a statistical fill, a manually entered value, leave unchanged, or delete the affected row. Only methods that make sense for the column are offered:

| Column type | Statistical methods |
|---|---|
| **Numeric** | Mean, Median, Mean (outliers excluded), Median (outliers excluded) |
| **Text / categorical** | Mode (most common value) |

With the *outliers excluded* variants, detected outliers are left out of the **calculation only**. The outliers themselves stay in the data until the user decides what to do with them.

**Identifier-like columns** (IDs, codes, names with almost all unique values) are treated differently. A missing ID cannot be estimated, because an invented ID would create fake data and could break record matching. For these columns CleanCore recommends deleting the affected row, though the user can still override this.

### 6.6 Quality Score

The Quality Score runs from 0 to 100 and is graded (Excellent, Good, Fair, Poor, Critical). It starts at 100 and subtracts penalties for measurable problems: missing values, duplicate rows, data-type issues and suspicious values. Outliers are shown as information only, because an outlier is not necessarily an error.

The score is calculated from the actual data, always comes with a factor-by-factor breakdown explaining why it has that value, and is reported **before and after cleaning** so the improvement is visible.

## 7. Cleaning Studio actions

| Group | Actions |
|---|---|
| **Row / Column** | Edit Cell, Delete Selected Row(s), Delete Selected Column(s), Rename Column |
| **Missing & Duplicates** | Fill Missing Values, Delete Rows by Column, Delete All Rows with Missing, Remove Exact Duplicates |
| **Types & Review** | Repair Data Type, Resolve Outlier, Resolve Suspicious Values |
| **Reset** | Reset to Original (restores the uploaded data; recorded in the history) |

Destructive actions show what will change (affected rows and columns, before and after) before they are applied, and every action is logged in the Change History. After each action the analysis is recalculated, so the Issue Center, scores and charts always reflect the current data.

## 8. Comparing two datasets

Once both datasets are finalized, CleanCore compares them across several levels:

- **Schema:** added, removed and common columns, data-type changes, and possible column renames. A rename is only suggested when the evidence is strong, with wording such as "manual verification recommended".
- **Rows:** new, deleted, modified and unchanged records. Records are matched using a unique identifier column when one exists, otherwise by row position. The report always explains which matching method was used and its limits.
- **Cells:** for each modified record, the column with the Reference value and the Current value.
- **Statistics:** for numeric columns, count, mean, median, minimum, maximum, standard deviation, variance, quartiles, IQR and skewness. For categorical columns, unique counts, frequencies, proportions, and new or removed categories.
- **Quality:** the quality score, missing values and duplicates for each version.
- **Distribution drift:** a Kolmogorov-Smirnov (KS) test on numeric columns, reporting the statistic, p-value and an interpretation. Drift is never claimed just because two means differ, and a statistical difference is distinguished from a practically important one. Columns with too little data are reported as having insufficient data.

The **cleaning history** of each dataset and the **comparison between versions** are always kept separate, in the application and in the reports.

## 9. Reports and downloads

| Output | Format | Purpose |
|---|---|---|
| **Data Quality Report** | HTML | Interactive version for viewing on screen. |
| **Data Quality Report** | PDF | Formal, print-ready version for sharing or submission. |
| **Cleaned dataset** | CSV | The final working data, exactly as finalized. |
| **Missing Values Audit Log** | Excel (.xlsx) | Every originally missing cell, how it was resolved and its final value. |

In Compare mode there are separate reports for the Reference dataset and the Current dataset, plus a **Comparison Report**, and a cleaned CSV for each dataset.

A report opens with the **Quality Score** (before and after cleaning). It then covers dataset information, statistics, the issues that remain, the full cleaning history, key charts, and a short final summary. The HTML and PDF versions are generated from the same report data, so they always agree.

## 10. Visualization

- **Dataset Overview:** a set of automatic charts that summarize the whole dataset with no configuration: missing values by column, data-type distribution, a correlation heatmap (when there are enough numeric columns), a numeric distribution and a categorical breakdown.
- **Custom Chart Builder:** the user picks the chart type and columns. Only chart and column combinations that make sense are allowed (for example, no pie chart for a column with dozens of categories).
- **Saved gallery:** charts can be saved with their settings, revisited, deleted and exported as images.
- Every chart states which dataset state it is based on (original, working copy or finalized) and is never stale.

## 11. How it is built

```
Browser (HTML / CSS / JavaScript, Plotly charts)
        |  REST API calls
Python backend
        |
Analysis engine | Cleaning engine | Comparison engine | Visualization engine
        |
pandas, NumPy, SciPy
        |
Report engine (Jinja2 -> HTML -> PDF)
```

- **Frontend:** plain HTML5, CSS3 and JavaScript; Plotly for interactive charts.
- **Backend:** Python with a REST API; the Python code is the single authority for all analysis, so the browser never duplicates data logic.
- **Data processing:** pandas, NumPy and SciPy (statistics and the KS test).
- **Reports:** Jinja2 templates rendered to HTML, with PDF generated from the same report data.
- **Testing:** pytest.

Suggested project layout (your folders may differ slightly):

```
frontend/   index.html, css/, js/
backend/    app.py, routes/, services/, analysis/, cleaning/,
            comparison/, visualization/, reports/, models/, utils/
templates/  report templates
static/     css, js
tests/      pytest tests
```

**Safety:** uploaded files are validated and handled safely, no credentials are hard-coded or displayed, and technical errors are logged for developers while users see clear, readable messages.

## 12. Sample datasets for testing

Two ready-made Excel files are included for trying the application. They are built to contain a known number of each issue.

| File | Rows x columns | Contents |
|---|---|---|
| `cleancore_ds1_400rows_8cols.xlsx` | 400 x 8 | `customer_id`, `customer_name`, `date`, `product_category`, `age`, `income`, `purchase_amount`, `rating` |
| `cleancore_ds2_400rows_10cols.xlsx` | 400 x 10 | the same 8 columns plus `order_quantity` and `customer_segment` |

Each file contains **20 missing values, 10 suspicious values, 15 outliers, 10 exact duplicate rows and 4 data-type issues** (`age`, `income` and `purchase_amount` are whole-number columns containing a few decimals, and `rating` is numbers stored as text with a few non-numeric entries). The IDs, names and dates contain no errors.

Used together for Compare mode, they share 360 customers, 30 customers appear only in the first file, 30 are new in the second, and 70 shared records have changed values.

## 13. Running it locally

1. Install Python 3 and the project's dependencies (pandas, NumPy, SciPy, openpyxl, Plotly, Jinja2, the web framework used by the backend, a PDF generation library, and pytest for tests), for example with `pip install -r requirements.txt`.
2. Start the Python backend (for example `python backend/app.py`).
3. Open the address it prints in a browser. When run locally the application is served at `http://127.0.0.1:5000`.

Adjust the paths and commands above to match your project's actual layout.

## 14. Project status

CleanCore is under active development (status as of October 2026). The main workflow (upload, analyze, clean, review, finalize, report, and two-dataset comparison) is in place. Areas still being refined:

- the custom chart builder (selecting several columns per chart, stricter chart and column validation) and the polish of the overview charts;
- PDF report layout and alignment;
- matching records by identifier in comparisons;
- a clearer separation between *potential outliers* and *suspicious values*;
- the data-type repair workflow;
- overall visual polish across the three themes;
- a future login and account area.

## 15. Glossary

| Term | Meaning |
|---|---|
| **Working copy** | The editable version of the dataset. The original upload is never changed. |
| **Finalize** | The user's explicit approval that the working copy is ready for reporting. |
| **Imputation** | Filling a missing value with an estimate, such as the mean or median. |
| **IQR** | Interquartile range, the spread of the middle 50% of values. Values far outside it are flagged as potential outliers. |
| **Outlier** | A value statistically far from the rest of its column. Not necessarily an error. |
| **Identifier-like column** | A column whose values are almost all unique, such as an ID. |
| **Reference / Current** | The earlier (baseline) and newer versions of a dataset in a comparison. |
| **Drift** | A real change in how a column's values are distributed between two datasets. |
| **KS test** | The Kolmogorov-Smirnov test, a statistical test of whether two numeric distributions differ. |
| **Change History** | The audit log of every modification made to the working copy. |
