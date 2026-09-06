**LearnLens Architecture and Research Foundations**

LearnLens is a learning platform for introductory quantum computing. It combines course-grounded AI support, quantum simulation, learner modelling, and formal assessment.

This document presents the proposed final architecture. It identifies the ideas adopted from each academic source and explains their role in LearnLens. Existing features and proposed additions are distinguished below. The papers support individual design choices; the combined LearnLens architecture still requires evaluation.

**The research contributions guide how LearnLens teaches, records evidence, and makes decisions.**

1. **ITAS informs the coordination of specialist tutoring roles.**

   ITAS uses Video, Code, and Guidance agents, followed by a Synthesizer that combines their reports. A separate autograder checks submissions. LearnLens adopts clear responsibilities, structured exchanges, controlled simulation tools, and separate tutoring and assessment paths. These responsibilities operate through services within the LearnLens backend. ITAS is a preprint, and its five-student pilot provides limited evidence about educational outcomes. [1](https://arxiv.org/html/2604.24808v1)

2. **IntelliCode informs the shared learner model.**

   IntelliCode coordinates specialist agents around one versioned learner record. A central coordinator controls updates to that record. LearnLens adopts controlled updates, preserved learner snapshots, and a common record for hints and activity selection. Each estimate links to supporting or contradicting evidence. IntelliCode's evaluation uses simulated learners, so its results do not establish benefits for human students. [2](https://aclanthology.org/2026.eacl-demo.10/)

3. **RAGMan informs course-grounded tutoring.**

   RAGMan combines assignment-specific knowledge bases, retrieved passages, conversation history, and tutor instructions. LearnLens adopts retrieval restricted to the relevant course and task context. Generated tasks and feedback should reference the approved material used to produce them. Hint policies should support the learning goal and task format. RAGMan's classroom deployment was observational, so grade differences cannot establish a causal learning benefit. [3](https://arxiv.org/html/2407.15718v1)

4. **Quantum Computing for All informs the circuit learning workspace.**

   This paper embeds a visual circuit simulator within online course activities. Its exercises combine configurable gates, reference circuits, hints, and stored attempts. LearnLens adopts an integrated workspace containing instructions, circuit editing, simulation results, explanations, and feedback. Controls can appear as the course introduces them. LearnLens extends this approach by linking circuit evidence to learner estimates and formal assessment criteria. [4](https://arxiv.org/abs/2404.10328)

5. **AutoTutor informs dialogue and guided feedback.**

   AutoTutor uses expected answers, misconceptions, hints, and prompts to guide conversations. LearnLens adopts questions that reveal student reasoning and feedback that supports revision. The tutor should begin with a probing question or conceptual hint, then provide more detail when permitted. Learners should explain their thinking before receiving further guidance. This contribution informs the proposed Tutor Agent and the existing feedback workflow. [5](https://digitalcommons.memphis.edu/facpubs/7449/)

6. **The Four-Process Architecture informs the assessment structure.**

   Almond, Steinberg, and Mislevy separate activity selection, presentation, response processing, and summary scoring. LearnLens adopts these boundaries through task selection, task delivery, evidence interpretation, and result calculation. This prevents the student response from being treated as an assessment decision without an explicit evaluation step. LearnLens adds its own PASS or INCOMPLETE rules, frozen assessment versions, and authorised assessor review. [6](https://ejournals.bc.edu/index.php/jtla/article/view/1671)

7. **Self-RAG informs grounding checks.**

   Self-RAG checks retrieved material and generated text through learned reflection tokens. LearnLens adopts the distinction between source relevance, claim support, and response usefulness. Its feedback process should check whether cited material supports the associated claim. LearnLens uses separate validation and judging services; it does not implement Self-RAG's trained reflection-token method. The paper supports a design principle, rather than direct evidence of learning improvement. [7](https://proceedings.iclr.cc/paper_files/paper/2024/file/25f7be9694d7b32d5cc670927b8091e1-Paper-Conference.pdf)

8. **Andes informs useful learner modelling and step-level evidence.**

   Andes checks intermediate physics problem-solving steps and provides targeted hints. Its developers removed a learner model whose estimates rarely affected teaching decisions. LearnLens adopts the principle that each learner estimate should serve a defined teaching purpose. An estimate about a misconception should lead to a suitable question, hint, or follow-up activity. Intermediate predictions, circuit changes, explanations, and revisions provide the evidence for those decisions. [8](https://www.oli.cmu.edu/wp-content/uploads/2012/05/VanLehn_2005_Andes_Physics_Tutoring_System.pdf)

9. **Research on AI judges informs the quality assurance process.**

   Zheng and colleagues identify biases and reasoning limits in language models used as judges. LearnLens therefore treats AI judging as a screening step. Basic validation, source checks, simulation evidence, and expert review provide additional checks. Accepted feedback should be sampled for human review. Rejection and fallback rates should also be recorded. A successful quality check does not establish that the student passed an assessment. [9](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91f18a1287b398d378ef22505bf41832-Abstract-Datasets_and_Benchmarks.html)

**The final architecture uses a modular backend with a complete evidence-to-adaptation loop.**

The proposed deployment contains a React and TypeScript frontend, a FastAPI backend, and a durable background worker. Backend modules share persistent storage. Educational agent names describe responsibilities within this structure. They do not require separate servers.

The backend retains control over access, workflow order, tool use, and state changes. AI services produce bounded suggestions or structured outputs. They cannot directly change permissions, publish assessed tasks, or confirm formal results.

| Component | Responsibility in the final design |
|---|---|
| User workspaces | Provide student, educator, assessor, and administrator screens. Keep task instructions, circuit work, explanations, and feedback together. The backend checks access for every protected operation. |
| Course and task services | Manage courses, outcomes, prerequisites, sources, and task versions. Generated tasks remain drafts until reviewed. Assessed tasks require approved criteria and pass rules. |
| Source and retrieval services | Extract and store material with stable source references and locations. Retrieve relevant course material. Preserve the source versions used in each generated output. |
| Workflow coordinator and worker | Control processing order, timeouts, retries, and fallbacks. Save submissions and their jobs together. Use safe retries so interrupted processing cannot duplicate accepted work. |
| Quantum services | Validate supported circuit descriptions and run controlled Qiskit Aer simulations. Link results to the exact circuit, qubit order, measurement mapping, and simulator settings. |
| Evidence and learner services | Preserve observations and build versioned learner estimates. Record evidence links, uncertainty, assistance used, and the rules behind each estimate. A controlled update path protects the shared learner record. |
| Teaching and feedback services | Generate tasks, ask questions, provide hints, and produce grounded feedback. Check outputs before release. Select the next approved activity using prerequisites and learner evidence. |
| Formal assessment services | Evaluate approved criteria, apply pass rules, and prepare provisional results. Route unsupported criteria to human assessment. Authorised assessors control final decisions and record reasons. |

SQLite and serial processing remain suitable starting choices for the bounded prototype. Load testing should determine when database capacity or worker concurrency needs to increase. Uploaded files remain in separate persistent file storage.

Provider interfaces remain replaceable. Research runs must record the actual provider, model, prompt version, and rule version. Local template mode must be distinguishable from external AI generation.

**The learning process preserves evidence before using it to guide the next activity.**

The main learning flow is:

Learning outcome → Approved task → Student response → Preserved attempt → Source and simulation context → Checked feedback → Student revision → Updated learner record → Next activity

For a circuit task, the student first predicts the result and explains their reasoning. The platform records the circuit and its simulation output. Feedback addresses differences between the prediction, explanation, and observed behaviour. A later activity checks whether the learner can apply the concept with less support.

Observations, learner estimates, and teaching decisions remain separate. A record that the student requested three hints is an observation. A claim about independent understanding is an inference. Selecting another practice task is a teaching decision. Each inference and decision should link back to its evidence.

The initial learner model should track understanding, possible misconceptions, use of help, response to feedback, and transfer to new tasks. Rule-based uncertainty values remain labelled as estimates until their reliability has been tested. The pathway service must record why it selected each activity. [2](https://aclanthology.org/2026.eacl-demo.10/) [8](https://www.oli.cmu.edu/wp-content/uploads/2012/05/VanLehn_2005_Andes_Physics_Tutoring_System.pdf)

**Feedback checks and formal assessment follow separate decision paths.**

The feedback flow is:

Collect evidence → Generate feedback → Validate structure and references → Judge quality → Release feedback

LearnLens sets a limit of one regeneration after rejected feedback. A second rejection produces a fixed fallback. The grounding checks assess claim support as well as citation presence. [7](https://proceedings.iclr.cc/paper_files/paper/2024/file/25f7be9694d7b32d5cc670927b8091e1-Paper-Conference.pdf) Feedback for assessed tasks must follow an approved help policy.

The formal assessment flow is:

Preserved attempt → Criterion evidence → Approved evaluator → Pass-rule engine → Provisional decision → Authorised assessor review → Confirmed result

Each criterion receives MET, NOT_MET, or NOT_EVALUABLE. The formal outcome remains PASS or INCOMPLETE. Review state remains a separate field. Unknown evidence cannot become positive evidence through negation. An unknown mandatory criterion blocks an automatic PASS recommendation and requires review.

Frozen task and assessment versions preserve the basis of every attempt. Assessor actions require reasons and create audit records. Feedback approval, practice scores, and learner estimates cannot independently confirm a formal result. This applies the separation between response processing and result calculation described in the Four-Process Architecture. [6](https://ejournals.bc.edu/index.php/jtla/article/view/1671)

**Simulation evidence must match the claim being assessed.**

For small ideal circuits, exact reference probabilities can support suitable checks. Sampled measurement counts require tolerances. Matching output distributions alone cannot establish every quantum-state property or prove conceptual understanding. Each task needs checks suited to its learning outcome, alongside the student's explanation.

Only tasks supported by the available gates and simulator limits should be published. The proposed design retains controlled circuit descriptions as the execution boundary.

**The next implementation step is one complete, tested learning loop.**

The supplied description describes existing task generation, simulation, feedback checking, preserved attempts, and versioned assessment. The final design requires further work on learner-driven sequencing, complete tutor integration, assessed-feedback policy, and missing criterion evaluators.

The first implementation should cover one quantum learning outcome from task selection through revision and the next activity. Evaluation should check feedback accuracy, evidence links, assessment behaviour, and recovery after interrupted processing. Claims about learning improvement require unaided conceptual questions and transfer or delayed-retention tasks.

The numbered references used in this document are listed below.

1. Elhaimeur, I., & Chrisochoides, N. (2026). *ITAS: A Multi-Agent Architecture for LLM-Based Intelligent Tutoring*. arXiv preprint, arXiv:2604.24808. [Full text](https://arxiv.org/html/2604.24808v1).

2. David, J., & Ghosh, S. (2026). *IntelliCode: A Multi-Agent LLM Tutoring System with Centralized Learner Modeling*. Proceedings of EACL 2026, Volume 3: System Demonstrations, pp. 129-138. [Publication and paper](https://aclanthology.org/2026.eacl-demo.10/).

3. Ma, I., Krone Martins, A., & Lopes, C. V. (2024). *Integrating AI Tutors in a Programming Course*. Proceedings of the ACM Virtual Global Computing Education Conference, Volume 1, pp. 130-136. DOI: 10.1145/3649165.3690094. [Open author manuscript](https://arxiv.org/html/2407.15718v1).

4. Reinikainen, J., Stirbu, V., Heinosaari, T., Lappalainen, V., & Mikkonen, T. (2024). *Quantum Computing for All: Online Courses Built Around an Interactive Visual Quantum Circuit Simulator*. IEEE Computer Graphics and Applications, 44(5), pp. 67-75. DOI: 10.1109/MCG.2024.3444952. [Open author manuscript](https://arxiv.org/abs/2404.10328).

5. Graesser, A. C., Chipman, P., Haynes, B. C., & Olney, A. (2005). *AutoTutor: An Intelligent Tutoring System With Mixed-Initiative Dialogue*. IEEE Transactions on Education, 48(4), pp. 612-618. [University publication record](https://digitalcommons.memphis.edu/facpubs/7449/).

6. Almond, R. G., Steinberg, L. S., & Mislevy, R. J. (2002). *Enhancing the Design and Delivery of Assessment Systems: A Four-Process Architecture*. The Journal of Technology, Learning and Assessment, 1(5). [Journal article](https://ejournals.bc.edu/index.php/jtla/article/view/1671).

7. Asai, A., Wu, Z., Wang, Y., Sil, A., & Hajishirzi, H. (2024). *Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection*. International Conference on Learning Representations. [Published paper](https://proceedings.iclr.cc/paper_files/paper/2024/file/25f7be9694d7b32d5cc670927b8091e1-Paper-Conference.pdf).

8. VanLehn, K., et al. (2005). *The Andes Physics Tutoring System: Lessons Learned*. International Journal of Artificial Intelligence in Education, 15(3), pp. 147-204. [Full text](https://www.oli.cmu.edu/wp-content/uploads/2012/05/VanLehn_2005_Andes_Physics_Tutoring_System.pdf).

9. Zheng, L., et al. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*. Advances in Neural Information Processing Systems, 36, Datasets and Benchmarks Track. [Publication and paper](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91f18a1287b398d378ef22505bf41832-Abstract-Datasets_and_Benchmarks.html).
