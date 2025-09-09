## 1. Research Journal: Your Central Thesis Notebook

A structured checklist is essential for systematic validation, but research also requires discovery and synthesis. You need a space to connect ideas, note findings about competitors, and build your narrative—a "small thesis."

**Vision:**  
For each company, maintain a dedicated Research Journal: a free-form, date-stamped notebook to log thoughts, findings, and connections as they occur.

**Approaches & Trade-offs:**

- **Simple Approach:**  
    Add a single, massive "notes" field to the Company model.  
    - *Pros:* Very easy to implement.  
    - *Cons:* Unstructured; loses context of when or what the note relates to.

- **Robust Approach (Recommended):**  
    Create a new `JournalEntry` model with fields like `company_id`, `entry_date`, `title`, `content`, and optional tags (e.g., "Competitor Analysis," "Management," "Red Flag").  
    - *Pros:* True, time-stamped journal; track thinking over time; filter/search by tag.  
    - *Cons:* Requires a new database model and dedicated page.

**Recommendation:**  
Adopt the Robust Approach for a professional research tool.

---

## 2. Competitor Tracking: Understanding the Landscape

To analyze competitors, the application must first know which companies are competitors.

**Vision:**  
Formally link companies in your database as competitors, enabling powerful comparative analysis features.

**Approaches & Trade-offs:**

- **Simple Approach:**  
    Add a text field to the Company model for competitor tickers (e.g., "MSFT, ORCL").  
    - *Pros:* Simple to add.  
    - *Cons:* Plain text; no links to actual company objects; limited comparison features.

- **Robust Approach (Recommended):**  
    Implement a proper many-to-many relationship on the Company model, allowing direct links between Company objects.  
    - *Pros:* Architecturally correct; enables advanced features like side-by-side metric comparisons.  
    - *Cons:* More complex database setup.

**Recommendation:**  
The Robust Approach is necessary for advanced features.

---

## 3. Interactive Document Q&A: Your AI Research Assistant

Enhance document analysis with interactive Q&A.

**Vision:**  
While viewing any uploaded document (e.g., a 10-K), highlight text, ask a question (e.g., "What does this term mean?" or "Summarize this section"), and get an immediate answer from Gemini.

**Approaches & Trade-offs:**

- **Frontend:**  
    Integrate a browser-based PDF rendering library (like PDF.js) to display documents and capture text selections.
- **Backend:**  
    Add a route to accept the selected text and user's question, then send it to the Gemini API for an answer.

**Recommendation:**  
This is a "killer feature" for the future. Build "Competitor Tracking" and "Research Journal" first, as they provide the structure for storing Q&A insights.

---

## Next Steps: Proposed Plan

All three features are powerful and interconnected. The logical build order:

1. **Competitor Tracking:** Define relationships between companies.
2. **Research Journal:** Capture findings from competitor analysis and document Q&A.
3. **Interactive Document Q&A:** Feed insights directly into the Research Journal.

**Does this strategic plan work for you? If so, we can begin with Step 1: Competitor Tracking, starting with the database model changes.**


--- Fix Reduantancy.... Combine My Research projects and My companies page