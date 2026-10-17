import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Brain, CheckCircle2, LoaderCircle, RotateCcw } from 'lucide-react';

type Language = 'ta' | 'en';
type Difficulty = 'easy' | 'medium' | 'hard';
type KuralRecord = {
  id: number;
  paal: string;
  chapter_no: number;
  chapter_name: string;
  line1: string;
  line2: string;
  meaning_en: string | null;
  needs_human_review: boolean;
};
type VerseOption = { id: number; line1: string; line2: string };
type MemoryQuestion = {
  id: string;
  mode: Difficulty;
  prompt: string;
  choices?: Array<string | VerseOption>;
};
type MemoryResult = {
  correct: boolean;
  points: number;
  accuracy?: number;
  correct_answer: string | VerseOption;
  question_id: string;
  discrepancies?: Array<{ kind: string; answer: string; correct: string }>;
};
type MemoryQuiz = {
  id: string;
  difficulty: Difficulty;
  scope: {
    paal: string;
    chapter_no: number;
    chapter_name: string;
    range_start: number | null;
    range_end: number | null;
  };
  question: MemoryQuestion | null;
  progress: {
    current: number;
    total: number;
    attempted: number;
    correct: number;
    incorrect: number;
  };
  score: number;
  complete: boolean;
  last_result: MemoryResult | null;
};

const QUIZ_STORAGE_KEY = 'meikural-memory-quiz';
const labels = {
  ta: {
    heading: 'குறள்களை நினைவில் கொள்வோம்',
    intro: 'பால், அதிகாரம் மற்றும் குறள் வரம்பைத் தேர்ந்தெடுத்து வினாடி வினா மூலம் பயிற்சி செய்யுங்கள்.',
    paal: 'பால்',
    chapter: 'அதிகாரம்',
    range: 'குறள் வரம்பு (விருப்பம்)',
    from: 'தொடக்கம்',
    to: 'முடிவு',
    scope: 'தேர்ந்தெடுத்த பயிற்சி',
    start: 'வினாடி வினாவைத் தொடங்கு',
    difficulty: 'சிரமத்தைத் தேர்ந்தெடுக்கவும்',
    easy: 'எளிது',
    medium: 'நடுத்தரம்',
    hard: 'கடினம்',
    easyInfo: 'விடுபட்ட சொல்லைத் தேர்ந்தெடு',
    mediumInfo: 'சரிபார்க்கப்பட்ட தமிழ் பொருள் கிடைக்கும்போது இந்தப் பயிற்சி திறக்கப்படும்.',
    hardInfo: 'எண்ணைப் பார்த்து குறளைத் தேர்ந்தெடு',
    cancel: 'திரும்பு',
    score: 'மதிப்பெண்',
    progress: 'கேள்வி',
    correct: 'சரி',
    incorrect: 'தவறு',
    submit: 'பதிலைச் சமர்ப்பி',
    write: 'குறளை இங்கே எழுதுங்கள்',
    verifiedMeaning: 'சரிபார்க்கப்பட்ட பொருள்',
    reveal: 'சரியான பதில்',
    right: 'சரியான பதில்!',
    wrong: 'இந்த முறை சரியில்லை.',
    discrepancy: 'வேறுபாடுகள்',
    next: 'அடுத்த கேள்வி',
    result: 'வினாடி வினா முடிந்தது',
    accuracy: 'துல்லியம்',
    attempted: 'முயற்சிகள்',
    retry: 'மீண்டும் முயற்சி',
    different: 'வேறு வினாடி வினா',
    loading: 'குறள்கள் ஏற்றப்படுகின்றன…',
    loadError: 'குறள்களை ஏற்ற முடியவில்லை. மீண்டும் முயற்சிக்கவும்.',
    apiUnavailable: 'நினைவுப் பயிற்சி சேவை கிடைக்கவில்லை. VS Code முனையத்தில் `pnpm dev` இயக்கி, இரு சேவைகளும் தொடங்கிய பிறகு மீண்டும் முயற்சிக்கவும்.',
    sessionError: 'வினாடி வினா அமர்வை மீட்டெடுக்க முடியவில்லை. புதிய வினாடி வினாவைத் தொடங்கவும்.',
    answerError: 'பதிலைச் சமர்ப்பிக்க முடியவில்லை. மீண்டும் முயற்சிக்கவும்.',
    noMeaning: 'இந்தத் தேர்வில் சரிபார்க்கப்பட்ட பொருள் கிடைக்கவில்லை. வேறு அதிகாரத்தைத் தேர்ந்தெடுக்கவும்.',
    mediumUnavailable: 'இந்தப் பயிற்சிக்கான பழைய அமர்வு ஆங்கிலப் பொருளைப் பயன்படுத்துகிறது. தமிழில் உறுதிப்படுத்தப்பட்ட பொருள் கிடைக்கும் வரை அது திறக்கப்படாது; புதிய வினாடி வினாவைத் தொடங்கவும்.',
    storageError: 'இந்த உலாவியில் வினாடி வினா அமர்வைச் சேமிக்க முடியவில்லை.',
    placeholder: 'விடுபட்ட சொல்',
    points: 'புள்ளிகள்',
    exact: 'அனைத்துச் சொற்களும் சரியாக உள்ளன.',
  },
  en: {
    heading: 'Memorize the Kurals',
    intro: 'Choose a Paal, chapter, and optional Kural range, then practice with a quiz.',
    paal: 'Paal',
    chapter: 'Athigaram',
    range: 'Kural range (optional)',
    from: 'From',
    to: 'To',
    scope: 'Selected learning scope',
    start: 'Start Quiz',
    difficulty: 'Choose a difficulty',
    easy: 'Easy',
    medium: 'Medium',
    hard: 'Hard',
    easyInfo: 'Choose the missing word',
    mediumInfo: 'Write the Kural from its meaning',
    hardInfo: 'Identify the Kural by number',
    cancel: 'Back',
    score: 'Score',
    progress: 'Question',
    correct: 'Correct',
    incorrect: 'Incorrect',
    submit: 'Submit answer',
    write: 'Write the Kural here',
    verifiedMeaning: 'Verified meaning',
    reveal: 'Correct answer',
    right: 'Correct!',
    wrong: 'Not quite.',
    discrepancy: 'Differences',
    next: 'Next question',
    result: 'Quiz complete',
    accuracy: 'Accuracy',
    attempted: 'Attempted',
    retry: 'Retry quiz',
    different: 'Choose a different quiz',
    loading: 'Loading Kurals…',
    loadError: 'Could not load Kurals. Please try again.',
    apiUnavailable: 'The memory API route was not found. In the VS Code terminal, run `pnpm dev` and retry after both services start.',
    sessionError: 'Could not restore the quiz session. Start a new quiz.',
    answerError: 'Could not submit your answer. Please try again.',
    noMeaning: 'This scope has no verified English meanings. Choose another chapter.',
    mediumUnavailable: 'This saved quiz uses an English meaning and cannot be shown in the Tamil interface.',
    storageError: 'Could not save the quiz session in this browser.',
    placeholder: 'Missing word',
    points: 'points',
    exact: 'Every word matches.',
  },
} satisfies Record<Language, Record<string, string>>;

function localized(language: Language, tamil: string, english: string) {
  return language === 'ta' ? tamil : english;
}

async function readError(response: Response, fallback: string, notFound: string = fallback): Promise<Error> {
  const payload = await response.json().catch(() => null) as { detail?: string } | null;
  if (response.status === 404 && payload?.detail === 'Not Found') {
    return new Error(notFound);
  }
  return new Error(payload?.detail || fallback);
}

export function MemoryPanel({ language }: { language: Language }) {
  const copy = labels[language];
  const [records, setRecords] = useState<KuralRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [catalogError, setCatalogError] = useState(false);
  const [selectedPaal, setSelectedPaal] = useState('');
  const [selectedChapter, setSelectedChapter] = useState(0);
  const [rangeStart, setRangeStart] = useState('');
  const [rangeEnd, setRangeEnd] = useState('');
  const [choosingDifficulty, setChoosingDifficulty] = useState(false);
  const [quiz, setQuiz] = useState<MemoryQuiz | null>(null);
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [answerText, setAnswerText] = useState('');
  const [showFeedback, setShowFeedback] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    void fetch('/api/kurals/catalog')
      .then(async (response) => {
        if (!response.ok) throw await readError(response, copy.loadError);
        const catalog = await response.json() as KuralRecord[];
        if (!Array.isArray(catalog) || catalog.length !== 1330) {
          throw new Error(copy.loadError);
        }
        if (!active) return;
        setRecords(catalog);
        setSelectedPaal(catalog[0]?.paal ?? '');
        setSelectedChapter(catalog[0]?.chapter_no ?? 0);
      })
      .catch((cause: unknown) => {
        console.error('Could not load the Kural memory catalog.', cause);
        if (active) setCatalogError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [copy.loadError]);

  useEffect(() => {
    let active = true;
    let quizId: string | null;
    try {
      quizId = sessionStorage.getItem(QUIZ_STORAGE_KEY);
    } catch (cause) {
      console.error('Could not read the saved memory quiz session.', cause);
      setError(copy.storageError);
      return;
    }
    if (!quizId) return;
    void fetch(`/api/memory/quizzes/${encodeURIComponent(quizId)}`)
      .then(async (response) => {
        if (!response.ok) throw await readError(response, copy.sessionError, copy.apiUnavailable);
        return response.json() as Promise<MemoryQuiz>;
      })
      .then((savedQuiz) => {
        if (!active) return;
        if (savedQuiz.difficulty === 'medium') {
          sessionStorage.removeItem(QUIZ_STORAGE_KEY);
          setError(copy.mediumUnavailable);
          return;
        }
        setQuiz(savedQuiz);
        setShowFeedback(false);
      })
      .catch((cause: unknown) => {
        console.error('Could not restore the saved memory quiz session.', cause);
        if (!active) return;
        try {
          sessionStorage.removeItem(QUIZ_STORAGE_KEY);
        } catch (storageCause) {
          console.error('Could not clear the expired memory quiz session.', storageCause);
        }
        setError(cause instanceof Error ? cause.message : copy.sessionError);
      });
    return () => { active = false; };
  }, [copy.mediumUnavailable, copy.sessionError, copy.storageError]);

  const paals = useMemo(() => [...new Set(records.map((record) => record.paal))], [records]);
  const chapters = useMemo(
    () => records.filter((record) => record.paal === selectedPaal)
      .filter((record, index, all) => all.findIndex((candidate) => candidate.chapter_no === record.chapter_no) === index),
    [records, selectedPaal],
  );
  const scopeRecords = useMemo(
    () => records.filter((record) => record.paal === selectedPaal && record.chapter_no === selectedChapter),
    [records, selectedPaal, selectedChapter],
  );
  const scopeChapter = chapters.find((chapter) => chapter.chapter_no === selectedChapter);
  const scopeText = scopeChapter
    ? `${selectedPaal} · ${scopeChapter.chapter_name}${rangeStart && rangeEnd ? ` · ${copy.from} ${rangeStart}–${rangeEnd}` : ''}`
    : '';

  const storeQuiz = (updatedQuiz: MemoryQuiz) => {
    try {
      sessionStorage.setItem(QUIZ_STORAGE_KEY, updatedQuiz.id);
    } catch (cause) {
      console.error('Could not save the memory quiz session.', cause);
      setError(copy.storageError);
      return false;
    }
    setQuiz(updatedQuiz);
    setShowFeedback(Boolean(updatedQuiz.last_result));
    setSelectedOption(null);
    setAnswerText('');
    setError('');
    return true;
  };

  const changePaal = (paal: string) => {
    const firstChapter = records.find((record) => record.paal === paal);
    setSelectedPaal(paal);
    setSelectedChapter(firstChapter?.chapter_no ?? 0);
    setRangeStart('');
    setRangeEnd('');
    setError('');
  };

  const startQuiz = async (
    difficulty: Difficulty,
    scope = {
      paal: selectedPaal,
      chapter_no: selectedChapter,
      range_start: rangeStart ? Number(rangeStart) : null,
      range_end: rangeEnd ? Number(rangeEnd) : null,
    },
  ) => {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/api/memory/quizzes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          paal: scope.paal,
          chapter_no: scope.chapter_no,
          difficulty,
          ...(scope.range_start !== null && scope.range_end !== null
            ? { range_start: scope.range_start, range_end: scope.range_end }
            : {}),
        }),
      });
      if (!response.ok) throw await readError(response, copy.sessionError, copy.apiUnavailable);
      const startedQuiz = await response.json() as MemoryQuiz;
      if (storeQuiz(startedQuiz)) setChoosingDifficulty(false);
    } catch (cause) {
      console.error('Could not start the Kural memory quiz.', cause);
      setError(cause instanceof Error ? cause.message : copy.sessionError);
    } finally {
      setBusy(false);
    }
  };

  const submitAnswer = async () => {
    if (!quiz?.question || busy) return;
    const question = quiz.question;
    const isMedium = quiz.difficulty === 'medium';
    if (isMedium ? !answerText.trim() : selectedOption === null) return;
    setBusy(true);
    setError('');
    try {
      const response = await fetch(`/api/memory/quizzes/${encodeURIComponent(quiz.id)}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question_id: question.id,
          ...(isMedium ? { answer_text: answerText } : { answer_index: selectedOption }),
        }),
      });
      if (!response.ok) throw await readError(response, copy.answerError, copy.apiUnavailable);
      const answeredQuiz = await response.json() as MemoryQuiz;
      setQuiz(answeredQuiz);
      setShowFeedback(Boolean(answeredQuiz.last_result));
      setSelectedOption(null);
      setAnswerText('');
    } catch (cause) {
      console.error('Could not submit a Kural memory quiz answer.', cause);
      setError(cause instanceof Error ? cause.message : copy.answerError);
    } finally {
      setBusy(false);
    }
  };

  const clearQuiz = () => {
    try {
      sessionStorage.removeItem(QUIZ_STORAGE_KEY);
    } catch (cause) {
      console.error('Could not clear the saved memory quiz session.', cause);
      setError(copy.storageError);
      return;
    }
    setQuiz(null);
    setChoosingDifficulty(false);
    setShowFeedback(false);
    setSelectedOption(null);
    setAnswerText('');
    setError('');
  };

  const retryQuiz = () => {
    if (!quiz) return;
    void startQuiz(quiz.difficulty, {
      paal: quiz.scope.paal,
      chapter_no: quiz.scope.chapter_no,
      range_start: quiz.scope.range_start,
      range_end: quiz.scope.range_end,
    });
  };

  if (loading) {
    return <div className="flex items-center gap-2 rounded-2xl border border-border bg-card p-6 text-sm text-muted-foreground"><LoaderCircle className="animate-spin" size={17} />{copy.loading}</div>;
  }
  if (catalogError) {
    return <div className="rounded-2xl border border-destructive/30 bg-card p-6 text-sm text-destructive">{copy.loadError}<button className="ml-3 underline" onClick={() => window.location.reload()}>{copy.retry}</button></div>;
  }

  return <div className="space-y-6" data-testid="memory-panel" aria-busy={busy}>
    <section className="rounded-[22px] border border-border bg-card p-5 shadow-[0_8px_32px_hsl(36_26%_45%/.05)] sm:p-7">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary"><Brain size={19} /></span>
        <div><p className="font-data text-[10px] uppercase tracking-[.18em] text-muted-foreground">{localized(language, 'நினைவுப் பயிற்சி', 'MEMORY PRACTICE')}</p><h2 className="mt-1 font-display text-[24px] tracking-[-.02em]">{copy.heading}</h2><p className="mt-2 text-[13px] leading-6 text-muted-foreground">{copy.intro}</p></div>
      </div>
      {!quiz && <div className="mt-6 space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-semibold">{copy.paal}
            <select className="mt-2 h-11 w-full rounded-xl border border-input bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/15" value={selectedPaal} onChange={(event) => changePaal(event.target.value)} data-testid="memory-paal">
              {paals.map((paal) => <option key={paal} value={paal}>{paal}</option>)}
            </select>
          </label>
          <label className="text-sm font-semibold">{copy.chapter}
            <select className="mt-2 h-11 w-full rounded-xl border border-input bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/15" value={selectedChapter} onChange={(event) => { setSelectedChapter(Number(event.target.value)); setRangeStart(''); setRangeEnd(''); }} data-testid="memory-chapter">
              {chapters.map((chapter) => <option key={chapter.chapter_no} value={chapter.chapter_no}>{chapter.chapter_no}. {chapter.chapter_name}</option>)}
            </select>
          </label>
        </div>
        <fieldset>
          <legend className="text-sm font-semibold">{copy.range}</legend>
          <div className="mt-2 grid grid-cols-2 gap-3">
            <label className="text-xs text-muted-foreground">{copy.from}
              <select className="mt-1 h-10 w-full rounded-xl border border-input bg-background px-3 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/15" value={rangeStart} onChange={(event) => setRangeStart(event.target.value)} data-testid="memory-range-start">
                <option value="">—</option>{scopeRecords.map((record) => <option key={record.id} value={record.id}>{record.id}</option>)}
              </select>
            </label>
            <label className="text-xs text-muted-foreground">{copy.to}
              <select className="mt-1 h-10 w-full rounded-xl border border-input bg-background px-3 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/15" value={rangeEnd} onChange={(event) => setRangeEnd(event.target.value)} data-testid="memory-range-end">
                <option value="">—</option>{scopeRecords.map((record) => <option key={record.id} value={record.id}>{record.id}</option>)}
              </select>
            </label>
          </div>
        </fieldset>
        <div className="rounded-xl bg-muted/60 p-4"><p className="font-data text-[10px] uppercase tracking-[.16em] text-muted-foreground">{copy.scope}</p><p className="mt-1 text-sm font-semibold">{scopeText}</p></div>
        {!choosingDifficulty
          ? <button className="min-h-11 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground transition hover:opacity-90 disabled:opacity-50" disabled={!scopeRecords.length || Boolean(rangeStart) !== Boolean(rangeEnd) || Boolean(rangeStart && rangeEnd && Number(rangeStart) > Number(rangeEnd))} onClick={() => { setChoosingDifficulty(true); setError(''); }} data-testid="memory-start-quiz">{copy.start}</button>
          : <div className="space-y-3">
            <div className="flex items-center justify-between"><h3 className="font-display text-lg">{copy.difficulty}</h3><button className="text-xs font-semibold text-muted-foreground underline" onClick={() => setChoosingDifficulty(false)}>{copy.cancel}</button></div>
            <div className="grid gap-3 sm:grid-cols-3">
              {(['easy', 'medium', 'hard'] as const).map((difficulty) => <button key={difficulty} disabled={busy || difficulty === 'medium'} onClick={() => { if (difficulty !== 'medium') void startQuiz(difficulty); }} className="rounded-xl border border-border bg-background p-4 text-left transition hover:border-primary hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50" data-testid={`memory-difficulty-${difficulty}`}><span className="font-display text-base">{copy[difficulty]}</span><span className="mt-1 block text-xs leading-5 text-muted-foreground">{copy[`${difficulty}Info`]}</span></button>)}
            </div>
          </div>}
      </div>}
      {quiz && <div className="mt-6 space-y-5" data-testid="memory-quiz">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-muted/60 p-4">
          <div><p className="font-data text-[10px] uppercase tracking-[.16em] text-muted-foreground">{copy.scope}</p><p className="mt-1 text-sm font-semibold">{quiz.scope.paal} · {quiz.scope.chapter_name}{quiz.scope.range_start !== null && quiz.scope.range_end !== null ? ` · ${quiz.scope.range_start}–${quiz.scope.range_end}` : ''} · {copy[quiz.difficulty]}</p></div>
          <div className="flex gap-4 text-xs font-semibold"><span>{copy.score}: {quiz.score}</span><span>{copy.progress}: {quiz.progress.current}/{quiz.progress.total}</span><span>{copy.correct}: {quiz.progress.correct}</span><span>{copy.incorrect}: {quiz.progress.incorrect}</span></div>
        </div>
        {quiz.complete
          ? <div className="rounded-2xl border border-primary/20 bg-primary/5 p-5" data-testid="memory-results">
            <CheckCircle2 className="text-primary" size={22} /><h3 className="mt-2 font-display text-xl">{copy.result}</h3>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <ResultStat label={copy.score} value={`${quiz.score}/${quiz.progress.total * 10}`} />
              <ResultStat label={copy.accuracy} value={`${quiz.progress.attempted ? Math.round((quiz.progress.correct / quiz.progress.attempted) * 100) : 0}%`} />
              <ResultStat label={copy.correct} value={String(quiz.progress.correct)} />
              <ResultStat label={copy.attempted} value={String(quiz.progress.attempted)} />
            </div>
            <div className="mt-5 flex flex-wrap gap-3"><button disabled={busy} onClick={retryQuiz} className="flex min-h-10 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50"><RotateCcw size={15} />{copy.retry}</button><button onClick={clearQuiz} className="min-h-10 rounded-xl border border-border px-4 text-sm font-semibold">{copy.different}</button></div>
          </div>
          : quiz.question && !showFeedback && <div className="rounded-2xl border border-border bg-background p-5">
            {quiz.difficulty === 'medium'
              ? <><p className="font-data text-[10px] uppercase tracking-[.16em] text-muted-foreground">{copy.verifiedMeaning}</p><p className="mt-2 text-base leading-7">{quiz.question.prompt}</p><textarea className="mt-4 min-h-32 w-full rounded-xl border border-input bg-card p-3 font-sans text-base leading-8 outline-none focus:border-primary focus:ring-2 focus:ring-primary/15" value={answerText} onChange={(event) => setAnswerText(event.target.value)} placeholder={copy.write} aria-label={copy.write} data-testid="memory-answer-text" /></>
              : <><p className="font-data text-[10px] uppercase tracking-[.16em] text-muted-foreground">{quiz.difficulty === 'easy' ? copy.easyInfo : copy.hardInfo}</p><p className="mt-3 whitespace-pre-line font-serif text-xl leading-10" lang="ta" data-testid="memory-question">{quiz.question.prompt}</p>
                <div className="mt-4 grid gap-2">{quiz.question.choices?.map((choice, index) => <button key={typeof choice === 'string' ? `${choice}-${index}` : choice.id} type="button" disabled={showFeedback || busy} onClick={() => setSelectedOption(index)} className={`rounded-xl border p-3 text-left text-sm transition ${selectedOption === index ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'} disabled:cursor-default`} data-testid={`memory-option-${index}`} aria-pressed={selectedOption === index}>
                  {typeof choice === 'string' ? <span className="font-serif text-lg" lang="ta">{choice}</span> : <span className="font-serif text-lg leading-8" lang="ta">{choice.line1}<br />{choice.line2}</span>}
                </button>)}</div></>}
            {!showFeedback && <button disabled={busy || (quiz.difficulty === 'medium' ? !answerText.trim() : selectedOption === null)} onClick={() => { void submitAnswer(); }} className="mt-4 flex min-h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground disabled:opacity-50" data-testid="memory-submit">{busy && <LoaderCircle className="animate-spin" size={15} />}{copy.submit}</button>}
          </div>}
        {showFeedback && quiz.last_result && <div className={`rounded-2xl border p-5 ${quiz.last_result.correct ? 'border-emerald-600/25 bg-emerald-500/5' : 'border-amber-600/25 bg-amber-500/5'}`} data-testid="memory-feedback">
          <h3 className="font-semibold">{quiz.last_result.correct ? copy.right : copy.wrong} +{quiz.last_result.points} {copy.points}{quiz.last_result.accuracy !== undefined ? ` · ${quiz.last_result.accuracy}%` : ''}</h3>
          <p className="mt-3 font-data text-[10px] uppercase tracking-[.16em] text-muted-foreground">{copy.reveal}</p>
          {typeof quiz.last_result.correct_answer === 'string'
            ? <p className="mt-1 whitespace-pre-line font-serif text-lg leading-8" lang="ta">{quiz.last_result.correct_answer}</p>
            : <p className="mt-1 font-serif text-lg leading-8" lang="ta">{quiz.last_result.correct_answer.line1}<br />{quiz.last_result.correct_answer.line2}</p>}
          {quiz.difficulty === 'medium' && <div className="mt-3">
            <p className="text-xs font-semibold text-muted-foreground">{copy.discrepancy}</p>
            {quiz.last_result.discrepancies?.length
              ? <ul className="mt-2 space-y-1 text-sm">{quiz.last_result.discrepancies.map((part, index) => <li key={`${part.kind}-${index}`}><span className="font-semibold">{part.kind === 'insert' ? localized(language, 'விடுபட்டது:', 'Missing:') : part.kind === 'delete' ? localized(language, 'கூடுதலாக:', 'Extra:') : localized(language, 'மாற்றம்:', 'Change:')}</span> {part.answer || '—'} → <span lang="ta">{part.correct || '—'}</span></li>)}</ul>
              : <p className="mt-1 text-sm">{copy.exact}</p>}
          </div>}
          {!quiz.complete && <button className="mt-4 min-h-10 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground" onClick={() => setShowFeedback(false)} data-testid="memory-next">{copy.next}</button>}
        </div>}
      </div>}
      {error && <p role="alert" className="mt-4 flex items-start gap-2 rounded-xl border border-destructive/25 bg-destructive/5 p-3 text-sm text-destructive"><AlertCircle className="mt-0.5 shrink-0" size={16} />{error}{error === copy.storageError && quiz && <button onClick={clearQuiz} className="underline">{copy.different}</button>}</p>}
    </section>
  </div>;
}

function ResultStat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-background p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 font-display text-xl">{value}</p></div>;
}
