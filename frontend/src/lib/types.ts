export interface Course {
  id: number;
  user_id: number;
  code: string;
  title: string;
  total_marks: number;
  grading_scale: Record<string, unknown>;
  language: string;
}

export interface MarkingScheme {
  id: number;
  course_id: number;
  version: number;
  content: string;
  special_instructions: string | null;
  selection_rule: string | null;
}

export interface Batch {
  id: number;
  course_id: number;
  scheme_id: number;
  name: string;
  status: string;
}

export interface Script {
  id: number;
  batch_id: number;
  original_filename: string;
  page_count: number | null;
  student_name: string | null;
  matric_number: string | null;
  status: string;
  total_awarded: number | null;
  percentage: number | null;
  grade: string | null;
  needs_human_review: boolean;
}

export interface BatchDetail extends Batch {
  scripts: Script[];
}

export interface MarkPoint {
  scheme_point: string;
  decision: "AWARDED" | "PARTIAL" | "NOT AWARDED";
  marks: number;
  evidence: string;
  note: string;
}

export interface ReportQuestion {
  question: string;
  attempted: boolean;
  max_marks: number;
  awarded: number;
  provisional: boolean;
  mark_points: MarkPoint[];
  strengths: string;
  missing_points: string;
  errors: string;
  legibility_flags: string[];
}

export interface McqSection {
  present: boolean;
  answer_string: string;
  correct: number;
  wrong: number;
  blank: number;
  ambiguous: number;
  score: number;
}

export interface PageAnomaly {
  page: number;
  type: string;
  detail: string;
  affected_questions: string[];
}

export interface LowConfidenceSection {
  page: number;
  question: string;
  text: string;
  impact: string;
}

export interface OverallFeedback {
  concepts_understood: string;
  weak_areas: string;
  topics_to_revise: string;
  summary: string;
}

export interface MarkingReportJson {
  student_name: string | null;
  matric_number: string | null;
  course_code: string;
  needs_human_review: boolean;
  review_reasons: string[];
  questions: ReportQuestion[];
  mcq_section: McqSection;
  page_anomalies: PageAnomaly[];
  identity_anomalies: string[];
  total_awarded: number;
  total_possible: number;
  percentage: number;
  grade: string | null;
  low_confidence_sections: LowConfidenceSection[];
  overall_feedback: OverallFeedback;
}

export interface MarkingReportRecord {
  id: number;
  report_json: MarkingReportJson;
  transcription: string | null;
  human_readable: string | null;
  created_at: string;
}

export interface ScriptDetail {
  id: number;
  batch_id: number;
  original_filename: string;
  page_count: number | null;
  student_name: string | null;
  matric_number: string | null;
  status: string;
  total_awarded: number | null;
  percentage: number | null;
  grade: string | null;
  needs_human_review: boolean;
  latest_report: MarkingReportRecord | null;
}
