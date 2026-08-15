-- A real-shaped compatibility sample from the numeric LMS path. The three
-- legacy learner-result rows model a retired public-result table that existed
-- before the versioned assessment schema.  Quality Judge values remain in
-- their own compatibility namespace.

INSERT INTO users (email, password_hash, full_name, role, is_active)
VALUES
    ('legacy-assessment-educator@example.edu', 'legacy-hash', 'Legacy Educator', 'educator', 1),
    ('legacy-assessment-student@example.edu', 'legacy-hash', 'Legacy Student', 'student', 1);

INSERT INTO courses (
    id, educator_id, code, title, description, state, enrollment_open, created_at, updated_at
) VALUES (
    '00000000-0000-4000-8000-000000000481',
    (SELECT id FROM users WHERE email = 'legacy-assessment-educator@example.edu'),
    'LEG501',
    'Legacy assessment course',
    'A course retained for migration proof.',
    'draft',
    1,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT INTO course_modules (id, course_id, title, description, position, created_at, updated_at)
VALUES (
    '00000000-0000-4000-8000-000000000491',
    '00000000-0000-4000-8000-000000000481',
    'Legacy module',
    'A module retained for migration proof.',
    1,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT INTO learning_outcomes (
    id, module_id, title, statement, kind, week_number, position, created_at, updated_at
) VALUES (
    '00000000-0000-4000-8000-000000000496',
    '00000000-0000-4000-8000-000000000491',
    'Legacy outcome',
    'Explain the observed result.',
    'weekly',
    1,
    1,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT INTO learning_tasks (
    id, slug, title, module, description, instructions, task_type, difficulty, points, position,
    course_id, module_id, learning_outcome_id
) VALUES (
    '00000000-0000-4000-8000-000000000501',
    'legacy-assessment-task',
    'Legacy assessment task',
    'Legacy module',
    'A retained numeric-assessment response.',
    'Explain the observed result.',
    'short_answer',
    'introductory',
    0,
    1,
    '00000000-0000-4000-8000-000000000481',
    '00000000-0000-4000-8000-000000000491',
    '00000000-0000-4000-8000-000000000496'
);

INSERT INTO submission_drafts (id, student_id, task_id, answer, updated_at)
VALUES
    (
        '00000000-0000-4000-8000-000000000511',
        (SELECT id FROM users WHERE email = 'legacy-assessment-student@example.edu'),
        '00000000-0000-4000-8000-000000000501',
        'A high numeric legacy response.',
        CURRENT_TIMESTAMP
    );

INSERT INTO submission_attempts (
    id, draft_id, student_id, task_id, attempt_number, status, answer, score, feedback, submitted_at
) VALUES
    (
        '00000000-0000-4000-8000-000000000521',
        '00000000-0000-4000-8000-000000000511',
        (SELECT id FROM users WHERE email = 'legacy-assessment-student@example.edu'),
        '00000000-0000-4000-8000-000000000501',
        1,
        'completed',
        'A high numeric legacy response.',
        92,
        'Legacy feedback.',
        CURRENT_TIMESTAMP
    ),
    (
        '00000000-0000-4000-8000-000000000522',
        '00000000-0000-4000-8000-000000000511',
        (SELECT id FROM users WHERE email = 'legacy-assessment-student@example.edu'),
        '00000000-0000-4000-8000-000000000501',
        2,
        'submitted',
        'A low numeric legacy response.',
        15,
        'Legacy feedback.',
        CURRENT_TIMESTAMP
    );

CREATE TABLE legacy_learner_results (
    id TEXT PRIMARY KEY,
    response_version_id TEXT NOT NULL,
    result TEXT NOT NULL,
    score INTEGER
);

INSERT INTO legacy_learner_results (id, response_version_id, result, score)
VALUES
    ('legacy-learner-fail', '00000000-0000-4000-8000-000000000522', 'FAIL', 15),
    ('legacy-learner-pass', '00000000-0000-4000-8000-000000000521', 'PASS', 92),
    ('legacy-learner-unknown', '00000000-0000-4000-8000-000000000521', 'WITHHELD', 92);

CREATE TABLE legacy_quality_judge_results (
    id TEXT PRIMARY KEY,
    decision TEXT NOT NULL
);

INSERT INTO legacy_quality_judge_results (id, decision)
VALUES ('legacy-quality-judge-fail', 'fail');
