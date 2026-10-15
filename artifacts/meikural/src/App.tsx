import { createContext, useContext, useEffect, useRef, useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { getGetEvaluationResultsQueryKey, getGetHealthQueryKey, getGetKuralQueryKey, getHealthCheckQueryKey, useGuardAnswer, useGetEvaluationResults, useGetHealth, useGetKural, useHealthCheck, useVerifyQuote } from '@workspace/api-client-react';
import type { EvaluationResults, GuardQuote, Kural, Verification } from '@workspace/api-client-react';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';
import { Activity, ArrowRight, BookOpen, Check, ChevronDown, CircleHelp, Clipboard, FileSearch, Gauge, Leaf, LoaderCircle, Mic, MicOff, RefreshCw, ScanText, ShieldCheck, Sparkles, TriangleAlert, Upload } from 'lucide-react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from 'recharts';

const queryClient = new QueryClient();
type Tab = 'verify' | 'guard' | 'evaluation';
type Language = 'ta' | 'en';
type KuralVerse = { id: number; line1: string; line2: string };
type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string; confidence: number }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};
type SpeechRecognitionWindow = Window & {
  SpeechRecognition?: new () => SpeechRecognitionLike;
  webkitSpeechRecognition?: new () => SpeechRecognitionLike;
};
type VoiceState = 'idle' | 'listening' | 'processing' | 'error';
const LanguageContext = createContext<{ language: Language; setLanguage: (language: Language) => void }>({ language: 'ta', setLanguage: () => undefined });
const useLanguage = () => useContext(LanguageContext);
const text = (language: Language, tamil: string, english: string) => language === 'ta' ? tamil : english;

const tabs: { id: Tab; label: Record<Language, string>; icon: typeof ScanText; note: Record<Language, string> }[] = [
  { id: 'verify', label: { ta: 'சரிபார்', en: 'Verify' }, icon: FileSearch, note: { ta: 'ஒரு மேற்கோளைத் துல்லியமாகச் சரிபார்க்கவும்', en: 'Check a quotation against the corpus' } },
  { id: 'guard', label: { ta: 'பதில் சோதனை', en: 'Answer review' }, icon: ShieldCheck, note: { ta: 'முழுப் பதிலிலுள்ள மேற்கோள்களைத் தேடவும்', en: 'Find quotations throughout an answer' } },
  { id: 'evaluation', label: { ta: 'மதிப்பீடு', en: 'Evaluation' }, icon: Gauge, note: { ta: 'தொகுப்பின் செயல்திறனைக் காண்க', en: 'Review corpus-checking performance' } },
];

function Home() {
  const { language, setLanguage } = useLanguage();
  const [activeTab, setActiveTab] = useState<Tab>('verify');
  const [verses, setVerses] = useState<KuralVerse[]>([]);
  const [verseIndex, setVerseIndex] = useState(0);
  const [versesError, setVersesError] = useState(false);
  const health = useGetHealth({ query: { queryKey: getGetHealthQueryKey() } });
  const healthz = useHealthCheck({ query: { queryKey: getHealthCheckQueryKey() } });
  const apiOnline = Boolean(health.data || healthz.data);
  useEffect(() => {
    let active = true;
    void fetch('/api/kurals/verses')
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not load Kural verses (${response.status}).`);
        const records = await response.json() as KuralVerse[];
        if (records.length !== 1330) throw new Error(`Expected 1330 Kural verses, received ${records.length}.`);
        if (active) setVerses(records);
      })
      .catch((error: unknown) => {
        console.error('Could not load Kural verses for the home-page ticker.', error);
        if (active) setVersesError(true);
      });
    return () => { active = false; };
  }, []);
  useEffect(() => {
      if (verses.length === 0) return;
      const timer = window.setInterval(() => {
        setVerseIndex((index) => (index + 1) % verses.length);
      }, 3000);
      return () => window.clearInterval(timer);
  }, [verses.length]);
  return (
    <main className="grain min-h-[100dvh] overflow-hidden bg-background text-foreground">
      <div className="mx-auto flex min-h-[100dvh] max-w-[1440px]">
        <aside className="hidden w-[248px] shrink-0 flex-col justify-between border-r border-sidebar-border bg-sidebar px-6 py-7 text-sidebar-foreground md:flex">
          <div>
            <Brand />
            <div className="mt-14">
              <p className="mb-3 px-3 font-data text-[10px] uppercase tracking-[.2em] text-sidebar-foreground/45">{text(language, 'கருவிகள்', 'Tools')}</p>
              <nav className="space-y-1" aria-label={text(language, 'மெய்க்குறள் கருவிகள்', 'Meikural tools')}>
                {tabs.map((tab, index) => {
                  const Icon = tab.icon;
                  return <button key={tab.id} data-testid={`tab-${tab.id}`} onClick={() => setActiveTab(tab.id)} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition-colors ${activeTab === tab.id ? 'bg-sidebar-accent text-sidebar-accent-foreground' : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground'}`}>
                    <Icon size={17} strokeWidth={1.8} />
                    <span className="flex-1 text-sm font-medium">{tab.label[language]}</span>
                    {activeTab === tab.id && <span className="h-1.5 w-1.5 rounded-full bg-sidebar-primary" />}
                    <span className="sr-only">{text(language, `பிரிவு ${index + 1}`, `Section ${index + 1}`)}</span>
                  </button>;
                })}
              </nav>
            </div>
            <div className="mt-12 rounded-2xl border border-sidebar-border/80 bg-sidebar-accent/35 p-4">
              <div className="flex items-center gap-2 text-sidebar-primary"><Leaf size={15} /><span className="font-data text-[10px] uppercase tracking-[.18em]">{text(language, 'எங்கள் உறுதி', 'Our commitment')}</span></div>
              <p className="mt-3 text-[13px] leading-6 text-sidebar-foreground/75">{text(language, 'பொருத்தம் இல்லாததால் மேற்கோள் தவறானது என்று சொல்ல முடியாது. தொகுப்பில் தேடுகிறோம்; உறுதிப்படுத்த தமிழ் அறிஞரிடம் ஆலோசிக்கவும்.', 'A missing match does not prove a quotation is false. We search this corpus; consult a Tamil scholar for confirmation.')}</p>
            </div>
          </div>
          <div className="border-t border-sidebar-border pt-5">
            <div className="flex items-center gap-2.5">
              <span className={`h-2 w-2 rounded-full ${health.isError && healthz.isError ? 'bg-amber-300' : apiOnline ? 'bg-emerald-300' : 'bg-sidebar-primary animate-pulse'}`} />
              <span className="text-xs text-sidebar-foreground/70" data-testid="status-api">{health.isError && healthz.isError ? text(language, 'சேவை கிடைக்கவில்லை', 'Service unavailable') : apiOnline ? text(language, 'குறள் தொகுப்புடன் இணைக்கப்பட்டது', 'Connected to the Kural corpus') : text(language, 'தொகுப்புடன் இணைக்கிறது…', 'Connecting to corpus…')}</span>
            </div>
            <p className="mt-3 font-data text-[10px] tracking-wide text-sidebar-foreground/40">{text(language, 'திருக்குறள் · 1330 குறள்கள்', 'Tirukkural · 1,330 couplets')}</p>
          </div>
        </aside>
        <section className="min-w-0 flex-1">
          <header className="sticky top-0 z-20 flex h-[68px] items-center justify-between border-b border-border/80 bg-background/95 px-5 backdrop-blur-md sm:px-8 lg:px-12">
            <div className="flex items-center gap-3 md:hidden"><Brand compact /></div>
            <p className="hidden font-data text-[10px] uppercase tracking-[.2em] text-muted-foreground md:block">{text(language, 'மரபுச் செல்வத்தை மதிக்கும் தேடல்', 'A search that respects literary heritage')}</p>
            <div className="flex items-center gap-3"><div className="flex items-center gap-2 text-xs text-muted-foreground"><span className={`h-1.5 w-1.5 rounded-full ${apiOnline ? 'bg-primary' : 'bg-amber-500'}`} /><span data-testid="text-service-state">{health.isError && healthz.isError ? text(language, 'சேவை கிடைக்கவில்லை', 'Service unavailable') : apiOnline ? text(language, 'தொகுப்பு இணைப்பில் உள்ளது', 'Corpus connected') : text(language, 'சேவையைச் சரிபார்க்கிறது…', 'Checking service…')}</span></div><button type="button" onClick={() => setLanguage(language === 'ta' ? 'en' : 'ta')} className="rounded-lg border border-border px-2.5 py-1.5 text-xs font-semibold text-foreground hover:bg-muted" aria-label={text(language, 'ஆங்கிலத்திற்கு மாற்றவும்', 'Switch to Tamil')}>{language === 'ta' ? 'English' : 'தமிழ்'}</button></div>
          </header>
          <div className="mx-auto max-w-[1080px] px-5 pb-14 pt-9 sm:px-8 sm:pt-12 lg:px-12">
            <section className="hero-thiruvalluvar relative mb-9 min-h-[330px] overflow-hidden rounded-[24px] bg-[#15382f] text-[#f7f2e7] shadow-[0_18px_50px_rgba(21,56,47,.18)] sm:min-h-[345px] lg:min-h-[460px] xl:min-h-[480px]" style={{ backgroundImage: "linear-gradient(90deg, rgba(15, 43, 36, .97) 0%, rgba(15, 43, 36, .84) 38%, rgba(15, 43, 36, .18) 100%), url('/thiruvalluvar-statue.jpg')" }} data-testid="hero-thiruvalluvar">
              <div className="relative z-10 max-w-[650px] px-6 pb-24 pt-7 sm:px-9 sm:pb-28 sm:pt-9">
                <div className="flex items-center gap-2 font-data text-[10px] uppercase tracking-[.22em] text-[#e7c989]"><span className="h-px w-6 bg-[#e7c989]" />{text(language, 'தமிழ் இலக்கியம் · ஆதாரத்துடன்', 'Tamil literature · evidence first')}</div>
                <h1 className="mt-4 max-w-3xl font-display text-[2.1rem] leading-[1.12] tracking-[-.035em] sm:text-[3.15rem]">{language === 'ta' ? <>சொல்லின் <em className="font-display font-medium text-[#e7c989]">மூலத்தை</em> அறியுங்கள்.</> : <>Find the <em className="font-display font-medium text-[#e7c989]">source</em> of a quotation.</>}</h1>
                <p className="mt-4 max-w-[540px] text-[14px] leading-7 text-white/80">{text(language, 'மேற்கோளை உள்ளூர் திருக்குறள் தொகுப்புடன் ஒப்பிடுங்கள். அப்படியே பொருந்தினால் உறுதிப்படுத்தலாம்; சந்தேகம் இருந்தால் உறுதியற்றதாகவே தெரிவிப்போம்.', 'Compare a quotation with the local Tirukkural corpus. We confirm exact matches and report uncertain results as uncertain.')}</p>
              </div>
              {verses.length > 0
                ? <div className="absolute inset-x-0 bottom-0 z-10 min-h-[66px] border-t border-white/15 bg-[#102c25]/85 px-5 py-2.5 backdrop-blur-sm sm:px-8" aria-label={text(language, 'திருக்குறளின் 1330 குறள்களும் வரிசையாக நகர்கின்றன', 'All 1,330 Tirukkural couplets advance in order')} data-testid="verse-ticker">
                    <div key={verses[verseIndex]?.id} className="verse-ticker-slide flex items-center gap-3 sm:gap-5" aria-hidden="true">
                      <span className="shrink-0 font-data text-[9px] tracking-[.08em] text-[#e7c989]">#{verses[verseIndex]?.id}<span className="ml-1 text-white/55">/ 1330</span></span>
                      <p className="font-tamil text-[11px] leading-5 text-white/90 sm:text-[12px] sm:leading-6">{verses[verseIndex]?.line1}<br />{verses[verseIndex]?.line2}</p>
                    </div>
                  </div>
                : <div className="absolute inset-x-0 bottom-0 z-10 border-t border-white/15 bg-[#102c25]/85 px-6 py-3 font-data text-[10px] text-white/70">
                    {versesError ? text(language, 'குறள் ஓட்டத்தை ஏற்ற முடியவில்லை.', 'Could not load the Kural ticker.') : text(language, 'திருக்குறளின் 1330 குறள்களை ஏற்றுகிறது…', 'Loading all 1,330 Tirukkural couplets…')}
                  </div>}
            </section>
            <div className="mb-8 grid grid-cols-3 gap-1 rounded-2xl border border-border bg-card p-1.5 md:hidden" role="tablist" aria-label={text(language, 'மெய்க்குறள் கருவிகள்', 'Meikural tools')}>
              {tabs.map((tab) => { const Icon = tab.icon; return <button role="tab" aria-selected={activeTab === tab.id} key={tab.id} onClick={() => setActiveTab(tab.id)} data-testid={`mobile-tab-${tab.id}`} className={`flex min-h-12 items-center justify-center gap-1.5 rounded-xl px-2 text-[12px] font-semibold transition-all ${activeTab === tab.id ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:bg-muted'}`}><Icon size={15} />{tab.label[language]}</button>; })}
            </div>
            <div className="mb-7 hidden items-end justify-between border-b border-border md:flex">
              <div className="flex gap-7" role="tablist" aria-label={text(language, 'மெய்க்குறள் கருவிகள்', 'Meikural tools')}>
                {tabs.map((tab) => { const Icon = tab.icon; return <button role="tab" aria-selected={activeTab === tab.id} key={tab.id} onClick={() => setActiveTab(tab.id)} data-testid={`desktop-tab-${tab.id}`} className={`relative flex items-center gap-2 pb-4 text-[13px] font-semibold transition-colors ${activeTab === tab.id ? 'text-primary' : 'text-muted-foreground hover:text-foreground'}`}><Icon size={16} />{tab.label[language]}<span className={`absolute inset-x-0 -bottom-px h-[2px] transition-opacity ${activeTab === tab.id ? 'bg-primary opacity-100' : 'opacity-0'}`} /></button>; })}
              </div>
              <p className="mb-4 font-data text-[10px] text-muted-foreground">{tabs.find((item) => item.id === activeTab)?.note[language]}</p>
            </div>
            <div key={activeTab} className="reveal" role="tabpanel">
              {activeTab === 'verify' && <VerifyPanel />}
              {activeTab === 'guard' && <GuardPanel />}
              {activeTab === 'evaluation' && <EvaluationPanel />}
            </div>
            <footer className="mt-14 flex flex-col gap-3 border-t border-border pt-5 text-[11px] leading-5 text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
              <span>{text(language, 'திருக்குறளை அடிப்படையாகக் கொண்ட தேடல். தேடலின் வரம்புகளை உணர்ந்து செயல்படுகிறோம்.', 'Search based on the Tirukkural. We acknowledge the limits of corpus search.')}</span>
              <span className="font-data uppercase tracking-[.12em]">{text(language, 'தொகுப்பு தேடல் · உண்மைத்தன்மைக்கான முழு உத்தரவாதம் அல்ல', 'Corpus search · not a guarantee of authenticity')}</span>
            </footer>
          </div>
        </section>
      </div>
    </main>
  );
}

function Brand({ compact = false }: { compact?: boolean }) {
  const { language } = useLanguage();
  return <div className="flex items-center gap-3" data-testid="brand-kuralguard">
    <div className="flex h-10 w-10 items-center justify-center rounded-[13px] border border-sidebar-primary/40 bg-sidebar-primary/10 text-sidebar-primary"><BookOpen size={19} strokeWidth={1.7} /></div>
    <div><div className={`font-display text-[16px] leading-5 ${compact ? 'text-foreground' : 'text-sidebar-foreground'}`}>{text(language, 'மெய்க்குறள்', 'Meikural')}</div><div className={`mt-1 font-data text-[9px] uppercase tracking-[.19em] ${compact ? 'text-muted-foreground' : 'text-sidebar-foreground/45'}`}>{text(language, 'குறள் · உரைச் சரிபார்ப்பு', 'Kural · text verification')}</div></div>
  </div>;
}

async function readTamilFromImage(image: File): Promise<{ text: string; confidence: number }> {
  const { createWorker } = await import('tesseract.js');
  const bitmap = await createImageBitmap(image);
  const canvas = document.createElement('canvas');
  const scale = Math.min(2, 2400 / Math.max(bitmap.width, bitmap.height));
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const context = canvas.getContext('2d');
  if (!context) {
    bitmap.close();
    throw new Error('Could not prepare the image for Tamil text recognition.');
  }
  context.imageSmoothingQuality = 'high';
  context.filter = 'grayscale(1) contrast(1.25)';
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const preparedImage = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error('Could not prepare the image for Tamil text recognition.'));
    }, 'image/png');
  });
  const worker = await createWorker('tam');
  try {
    await worker.setParameters({ preserve_interword_spaces: '1', user_defined_dpi: '300' });
    const { data } = await worker.recognize(preparedImage, { rotateAuto: true });
    return { text: data.text.trim(), confidence: data.confidence };
  } finally {
    await worker.terminate();
  }
}

function formatVoiceTranscript(transcript: string): { text: string; splitCouplet: boolean } {
  const words = transcript.trim().split(/\s+/);
  if (words.length !== 7) return { text: transcript.trim(), splitCouplet: false };
  return {
    text: `${words.slice(0, 4).join(' ')}\n${words.slice(4).join(' ')}`,
    splitCouplet: true,
  };
}

function VerifyPanel() {
  const { language } = useLanguage();
  const [quoteText, setText] = useState('');
  const [claimedId, setClaimedId] = useState('');
  const [ocrState, setOcrState] = useState<'idle' | 'reading' | 'ready' | 'error'>('idle');
  const [ocrError, setOcrError] = useState<string | null>(null);
  const [ocrConfidence, setOcrConfidence] = useState<number | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [voiceMessage, setVoiceMessage] = useState<string | null>(null);
  const [voiceDraft, setVoiceDraft] = useState('');
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const hadFinalVoiceResultRef = useRef(false);
  const voiceFailureRef = useRef(false);
  const interimVoiceRef = useRef('');
  useEffect(() => () => {
    if (imagePreview) URL.revokeObjectURL(imagePreview);
  }, [imagePreview]);
  useEffect(() => () => {
    recognitionRef.current?.abort();
    recognitionRef.current = null;
  }, []);
  const verify = useVerifyQuote();
  const sampleOne = useGetKural(1, { query: { queryKey: getGetKuralQueryKey(1) } });
  const sampleTwo = useGetKural(2, { query: { queryKey: getGetKuralQueryKey(2) } });
  const sampleReady = Boolean(sampleOne.data && sampleTwo.data);
  const samples = sampleReady ? makeSamples(sampleOne.data!, sampleTwo.data!) : null;
  const lookupId = Number(claimedId);
  const kuralLookup = useGetKural(lookupId || 0, { query: { enabled: lookupId >= 1 && lookupId <= 1330, queryKey: getGetKuralQueryKey(lookupId || 0) } });
  const submitQuote = (quote: string) => { verify.mutate({ data: { text: quote, ...(claimedId ? { claimed_id: Number(claimedId) } : {}) } }); };
  const onSubmit = (event: FormEvent) => { event.preventDefault(); if (!quoteText.trim()) return; submitQuote(quoteText.trim()); };
  const onVoiceButton = () => {
    if (voiceState === 'listening') {
      setVoiceState('processing');
      setVoiceMessage(text(language, 'பேச்சைச் செயலாக்குகிறது…', 'Processing your speech…'));
      try {
        recognitionRef.current?.stop();
      } catch (error) {
        console.error('Could not stop Tamil speech recognition.', error);
        recognitionRef.current?.abort();
        recognitionRef.current = null;
        setVoiceState('error');
        setVoiceMessage(text(language, 'பதிவை நிறுத்த முடியவில்லை. மீண்டும் முயற்சிக்கவும்.', 'Could not stop recording. Please try again.'));
      }
      return;
    }
    if (voiceState === 'processing') return;
    if (!window.isSecureContext) {
      setVoiceState('error');
      setVoiceMessage(text(language, 'குரல் தேடலுக்கு பாதுகாப்பான இணைப்பு தேவை. HTTPS அல்லது localhost-ஐப் பயன்படுத்தவும்.', 'Voice search requires a secure connection. Use HTTPS or localhost.'));
      return;
    }
    if (!navigator.onLine) {
      setVoiceState('error');
      setVoiceMessage(text(language, 'குரல் அறிதலுக்கு இணைய இணைப்பு தேவை. இணையத்தைச் சரிபார்த்து மீண்டும் முயற்சிக்கவும்.', 'Speech recognition needs an internet connection. Check your connection and try again.'));
      return;
    }
    const SpeechRecognition = (window as SpeechRecognitionWindow).SpeechRecognition
      ?? (window as SpeechRecognitionWindow).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceState('error');
      setVoiceMessage(text(language, 'இந்த உலாவியில் குரல் அறிதல் கிடைக்கவில்லை. தமிழில் தட்டச்சு செய்யவும் அல்லது படத்தைப் பதிவேற்றவும்.', 'Speech recognition is not available in this browser. Type in Tamil or upload an image instead.'));
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'ta-IN';
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      hadFinalVoiceResultRef.current = false;
      interimVoiceRef.current = '';
      voiceFailureRef.current = false;
      setVoiceDraft('');
      setVoiceState('listening');
      setVoiceMessage(text(language, 'தமிழில் பேசுங்கள். முடிந்ததும் நிறுத்து பொத்தானை அழுத்தவும்.', 'Speak in Tamil. Press Stop when you are finished.'));

      recognition.onresult = (event) => {
        let finalTranscript = '';
        let interimTranscript = '';
        for (let index = 0; index < event.results.length; index += 1) {
          const result = event.results[index];
          if (!result) continue;
          const recognizedText = result[0]?.transcript ?? '';
          if (result.isFinal) finalTranscript += `${recognizedText} `;
          else interimTranscript += `${recognizedText} `;
        }
        interimVoiceRef.current = interimTranscript.trim();
        setVoiceDraft(interimVoiceRef.current);
        if (finalTranscript.trim()) {
          const formattedTranscript = formatVoiceTranscript(finalTranscript);
          hadFinalVoiceResultRef.current = true;
          setText(formattedTranscript.text.slice(0, 5000));
          setVoiceDraft('');
          interimVoiceRef.current = '';
          setVoiceState('processing');
          setVoiceMessage(formattedTranscript.splitCouplet
            ? text(language, '7 சொற்கள் கண்டறியப்பட்டன: முதல் 4 சொற்கள் முதல் வரியிலும், அடுத்த 3 சொற்கள் இரண்டாம் வரியிலும். சரிபார்த்து, பிறகு சரிபார்ப்பை அழுத்தவும்.', 'Seven words detected and split into 4 words on line one and 3 on line two. Review the text, then click Verify.')
            : text(language, 'உரை கிடைத்தது. அதைத் திருத்தி, சரிபார்ப்பை அழுத்தவும்.', 'Transcript ready. Review or edit it, then click Verify.'));
        }
      };
      recognition.onerror = (event) => {
        const messages: Record<string, string> = {
          'not-allowed': text(language, 'மைக்ரோஃபோன் அனுமதி மறுக்கப்பட்டது. உலாவி அமைப்புகளில் மைக்ரோஃபோன் அனுமதியை இயக்கி மீண்டும் முயற்சிக்கவும்.', 'Microphone permission was denied. Allow microphone access in browser settings and try again.'),
          'service-not-allowed': text(language, 'உலாவியின் குரல் அறிதல் சேவை அனுமதிக்கப்படவில்லை.', 'The browser speech-recognition service is not allowed.'),
          'language-not-supported': text(language, 'உலாவியின் குரல் சேவை தமிழ் (ta-IN) மொழியை ஆதரிக்கவில்லை.', 'The browser speech service does not support Tamil (ta-IN).'),
          'no-speech': text(language, 'பேச்சு கேட்கப்படவில்லை. மைக்ரோஃபோனைச் சரிபார்த்து அமைதியான இடத்தில் மீண்டும் முயற்சிக்கவும்.', 'No speech was detected. Check your microphone and try again somewhere quieter.'),
          'audio-capture': text(language, 'மைக்ரோஃபோன் கிடைக்கவில்லை. அது இணைக்கப்பட்டுள்ளதா, வேறு செயலி பயன்படுத்தவில்லையா எனச் சரிபார்க்கவும்.', 'No microphone is available. Check that it is connected and not in use by another app.'),
          network: text(language, 'குரல் அறிதல் இணைப்பு தோல்வியடைந்தது. இணையத்தைச் சரிபார்த்து மீண்டும் முயற்சிக்கவும்.', 'Speech recognition connection failed. Check your internet connection and try again.'),
          aborted: text(language, 'குரல் பதிவு ரத்து செய்யப்பட்டது.', 'Voice recording was cancelled.'),
        };
        const message = messages[event.error] ?? text(language, 'குரல் உரையைப் புரிந்துகொள்ள முடியவில்லை. மீண்டும் முயற்சிக்கவும்.', 'Could not recognize the spoken words. Please try again.');
        voiceFailureRef.current = event.error !== 'aborted';
        setVoiceState(event.error === 'aborted' ? 'idle' : 'error');
        setVoiceMessage(message);
        if (event.error !== 'aborted') console.error('Tamil speech recognition failed:', event.error);
      };
      recognition.onend = () => {
        if (recognitionRef.current === recognition) recognitionRef.current = null;
        if (voiceFailureRef.current) return;
        if (hadFinalVoiceResultRef.current) {
          setVoiceState((current) => current === 'error' ? current : 'idle');
          return;
        }
        const partialTranscript = interimVoiceRef.current.trim();
        if (partialTranscript) {
          const formattedTranscript = formatVoiceTranscript(partialTranscript);
          setText(formattedTranscript.text.slice(0, 5000));
          setVoiceState('error');
          setVoiceMessage(formattedTranscript.splitCouplet
            ? text(language, 'பகுதி உரையில் 7 சொற்கள் இருந்ததால் அதை 4 + 3 எனப் பிரித்தோம். உரையைச் சரிபார்த்து, தேவையானால் திருத்தவும்.', 'The partial transcript had 7 words, so it was split 4 + 3. Review and correct it before verifying.')
            : text(language, 'பகுதி உரை மட்டுமே கிடைத்தது. அதைச் சரிபார்த்து, தேவையானால் திருத்தவும்.', 'Only a partial transcript was captured. Review and correct it before verifying.'));
        } else {
          setVoiceState('error');
          setVoiceMessage(text(language, 'பேச்சு கிடைக்கவில்லை. மீண்டும் பேசவும் அல்லது தமிழில் தட்டச்சு செய்யவும்.', 'No transcript was captured. Try speaking again or type in Tamil.'));
        }
      };
      recognitionRef.current = recognition;
      recognition.start();
    } catch (error) {
      console.error('Could not start Tamil speech recognition.', error);
      recognitionRef.current = null;
      setVoiceState('error');
      setVoiceMessage(text(language, 'மைக்ரோஃபோனைத் தொடங்க முடியவில்லை. அனுமதி மற்றும் உலாவி அமைப்புகளைச் சரிபார்க்கவும்.', 'Could not start the microphone. Check permission and browser settings.'));
    }
  };
  const onImageSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const image = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!image) return;
    if (!image.type.startsWith('image/')) {
      setOcrError(text(language, 'படக் கோப்பைத் தேர்ந்தெடுக்கவும்.', 'Choose an image file.'));
      setOcrState('error');
      return;
    }
    if (image.size > 10 * 1024 * 1024) {
      setOcrError(text(language, 'படம் 10 MB-ஐ விடச் சிறியதாக இருக்க வேண்டும்.', 'The image must be smaller than 10 MB.'));
      setOcrState('error');
      return;
    }

    setImagePreview(URL.createObjectURL(image));
    setOcrState('reading');
    setOcrError(null);
    setOcrConfidence(null);
    try {
      const { text: extractedText, confidence } = await readTamilFromImage(image);
      if (!extractedText) {
        setOcrError(text(language, 'படத்தில் படிக்கக்கூடிய தமிழ் உரை கிடைக்கவில்லை. தெளிவான படத்தை முயற்சிக்கவும்.', 'No readable Tamil text was found. Try a clearer image.'));
        setOcrState('error');
        return;
      }
      setOcrConfidence(confidence);
      setText(extractedText.slice(0, 5000));
      if (extractedText.length > 5000) {
        setOcrError(text(language, 'படத்திலிருந்து 5,000 எழுத்துகளுக்கு மேல் கிடைத்தது. உரை சுருக்கப்பட்டுள்ளது; சரிபார்ப்பதற்கு முன் அதைத் திருத்தவும்.', 'More than 5,000 characters were found. The text was shortened; review it before verifying.'));
        setOcrState('error');
        return;
      }
      setOcrState('ready');
    } catch (error) {
      console.error('Could not read Tamil text from the selected image.', error);
      setOcrError(text(language, 'படத்திலிருந்து உரையைப் படிக்க முடியவில்லை. மீண்டும் முயற்சிக்கவும்.', 'Could not read text from the image. Please try again.'));
      setOcrState('error');
    }
  };
  return <div className="grid gap-6 lg:grid-cols-[minmax(0,1.06fr)_minmax(320px,.94fr)]">
    <section className="rounded-[22px] border border-border bg-card p-5 shadow-[0_8px_32px_hsl(36_26%_45%/.05)] sm:p-7">
      <div className="flex items-start justify-between gap-3"><div><p className="font-data text-[10px] uppercase tracking-[.18em] text-muted-foreground">{text(language, '01 / ஒரு மேற்கோள்', '01 / Single quote')}</p><h2 className="mt-2 font-display text-[24px] tracking-[-.02em]">{text(language, 'ஒரு பகுதியைச் சரிபார்க்கவும்', 'Verify a passage')}</h2></div><span className="rounded-full bg-secondary px-3 py-1.5 font-data text-[10px] text-secondary-foreground">{text(language, 'உள்ளூர் தொகுப்பு', 'Local corpus')}</span></div>
      <form className="mt-7" onSubmit={onSubmit}>
        <label htmlFor="quote-input" className="mb-2 flex items-center justify-between text-[12px] font-semibold">{text(language, 'மேற்கோள் உரை', 'Quotation text')} <span className="text-right text-[10px] font-normal text-muted-foreground">{text(language, 'வரி 1: 4 சொற்கள் · வரி 2: 3 சொற்கள்', 'Line 1: 4 words · line 2: 3 words')}</span></label>
        <div className="mb-4 rounded-xl border border-dashed border-border bg-muted/35 px-4 py-3.5" aria-busy={ocrState === 'reading'}>
          <div className="flex flex-wrap items-center gap-3">
            <label htmlFor="quote-image" className={`inline-flex h-10 cursor-pointer items-center gap-2 rounded-lg border border-border bg-background px-3 text-[12px] font-semibold transition-colors hover:border-primary hover:text-primary ${ocrState === 'reading' ? 'pointer-events-none opacity-50' : ''}`}>
              {ocrState === 'reading' ? <LoaderCircle size={15} className="animate-spin" /> : <Upload size={15} />}
              {ocrState === 'reading' ? text(language, 'படத்தைப் படிக்கிறது…', 'Reading image…') : text(language, 'குறள் படத்தைப் பதிவேற்றவும்', 'Upload a Kural image')}
            </label>
            <input id="quote-image" type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={onImageSelected} disabled={ocrState === 'reading'} data-testid="input-quote-image" />
            <p className="text-[10px] leading-5 text-muted-foreground">{text(language, 'PNG, JPG அல்லது WebP · அதிகபட்சம் 10 MB', 'PNG, JPG, or WebP · 10 MB max')}</p>
          </div>
          <p className="mt-2 text-[10px] leading-5 text-muted-foreground">{text(language, 'படம் உங்கள் சாதனத்திலேயே செயலாக்கப்படும். கண்டறிந்த உரையைச் சரிபார்த்து திருத்தலாம்.', 'The image is processed on your device. You can review and edit the detected text.')}</p>
          {imagePreview && <img src={imagePreview} alt={text(language, 'பதிவேற்றிய குறள் படம்', 'Uploaded Kural screenshot')} className="mt-3 max-h-36 max-w-full rounded-lg border border-border object-contain" data-testid="image-quote-preview" />}
          {ocrState === 'ready' && <div role="status" className="mt-2 text-[11px] leading-5">
            <p className="font-semibold text-primary">{text(language, 'படத்திலிருந்து கண்டறிந்த உரை கீழே உள்ளது. அதைத் திருத்தி, சரிபார்ப்பை அழுத்தவும்.', 'Extracted text is below. Review or correct it, then click Verify.')}</p>
            {ocrConfidence !== null && <p className={ocrConfidence < 70 ? 'mt-1 text-amber-700' : 'mt-1 text-muted-foreground'}>{text(language, 'OCR நம்பிக்கை மதிப்பீடு', 'OCR confidence estimate')}: {Math.round(ocrConfidence)}%{ocrConfidence < 70 ? text(language, ' · உரையை கவனமாகச் சரிபார்க்கவும்.', ' · Check the text carefully.') : ''}</p>}
          </div>}
          {ocrError && <p role="alert" className="mt-2 text-[11px] leading-5 text-destructive">{ocrError}</p>}
        </div>
        <div className="relative">
          <textarea id="quote-input" data-testid="input-quote" value={quoteText} onChange={(event) => setText(event.target.value)} maxLength={5000} placeholder={text(language, 'மேற்கோள் உரையை இங்கே ஒட்டவும்…', 'Paste the quotation here…')} className="min-h-[164px] w-full resize-y rounded-xl border border-input bg-background px-4 py-3.5 pb-14 pr-28 text-[15px] leading-7 outline-none placeholder:text-muted-foreground/60 focus:border-primary focus:ring-2 focus:ring-primary/15" />
          <button
            type="button"
            onClick={onVoiceButton}
            disabled={voiceState === 'processing'}
            aria-label={voiceState === 'listening' ? text(language, 'பேச்சை நிறுத்தவும்', 'Stop listening') : voiceState === 'processing' ? text(language, 'பேச்சைச் செயலாக்குகிறது', 'Processing speech') : text(language, 'தமிழில் குரல் தேடல்', 'Search by speaking Tamil')}
            aria-pressed={voiceState === 'listening'}
            data-testid="button-voice-search"
            className={`absolute bottom-3 right-3 inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-[11px] font-semibold transition-colors disabled:cursor-wait disabled:opacity-70 ${voiceState === 'listening' ? 'animate-pulse bg-destructive text-destructive-foreground' : 'border border-border bg-card text-foreground hover:border-primary hover:text-primary'}`}
          >
            {voiceState === 'listening' ? <MicOff size={15} /> : voiceState === 'processing' ? <LoaderCircle size={15} className="animate-spin" /> : <Mic size={15} />}
            {voiceState === 'listening' ? text(language, 'நிறுத்து', 'Stop') : voiceState === 'processing' ? text(language, 'செயலாக்கம்', 'Processing') : text(language, 'பேசு', 'Speak')}
          </button>
        </div>
        <div className="mt-2 min-h-5" aria-live="polite" data-testid="voice-search-status">
          {voiceMessage && <p className={`text-[11px] leading-5 ${voiceState === 'error' ? 'text-destructive' : voiceState === 'listening' ? 'font-medium text-primary' : 'text-muted-foreground'}`}>{voiceMessage}</p>}
          {voiceDraft && voiceState === 'listening' && <p className="mt-1 font-tamil text-[12px] leading-6 text-muted-foreground">{voiceDraft}</p>}
        </div>
        <p className="mt-1 text-[10px] leading-4 text-muted-foreground">{text(language, 'குரலுக்கு உலாவி சேவையைப் பயன்படுத்துகிறது; ஆடியோவை மெய்க்குறள் பதிவு செய்யாது. சேவை வழங்குநரின் தனியுரிமைக் கொள்கை பொருந்தும்.', 'Voice uses your browser speech service; Meikural does not record or store audio. The provider’s privacy policy applies.')}</p>
        <div className="mt-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span className="font-data text-[9px] uppercase tracking-[.13em] text-muted-foreground">{text(language, 'தொகுப்பிலிருந்து மாதிரியைத் தேர்ந்தெடுக்கவும்', 'Choose a corpus sample')}</span>
            {!sampleReady && !sampleOne.isError && !sampleTwo.isError && <span className="font-data text-[9px] text-muted-foreground">{sampleOne.isLoading || sampleTwo.isLoading ? text(language, 'மாதிரிகளை ஏற்றுகிறது…', 'Loading samples…') : ''}</span>}
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => samples && setText(samples.real)} disabled={!samples} data-testid="button-sample-real" className="rounded-full border border-border bg-background px-3 py-1.5 text-[10px] font-semibold text-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-wait disabled:opacity-50">{text(language, 'உண்மையான குறள்', 'Authentic Kural')}</button>
            <button type="button" onClick={() => samples && setText(samples.spliced)} disabled={!samples} data-testid="button-sample-spliced" className="rounded-full border border-border bg-background px-3 py-1.5 text-[10px] font-semibold text-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-wait disabled:opacity-50">{text(language, 'இணைக்கப்பட்ட வரிகள்', 'Spliced lines')}</button>
            <button type="button" onClick={() => samples && setText(samples.replacement)} disabled={!samples || !samples.replacement} data-testid="button-sample-replacement" className="rounded-full border border-border bg-background px-3 py-1.5 text-[10px] font-semibold text-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-wait disabled:opacity-50">{text(language, 'ஒரு சொல் மாற்றம்', 'One word changed')}</button>
          </div>
          {(sampleOne.isError || sampleTwo.isError) && <p className="mt-2 text-[11px] leading-5 text-muted-foreground" data-testid="error-sample-source">{text(language, 'தொகுப்பு மாதிரிகளைப் பெற முடியவில்லை. சரிபார்க்க உரையை உள்ளிடலாம்.', 'Could not load corpus samples. You can enter text to verify.')}</p>}
          {sampleReady && !samples?.replacement && <p className="mt-2 text-[11px] leading-5 text-muted-foreground" data-testid="text-sample-replacement-unavailable">{text(language, 'இந்த இரண்டு குறள்களிலும் மாற்றிப் பயன்படுத்தத் தனித்த சொல் இல்லை.', 'These two Kurals have no distinct word to swap.')}</p>}
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
          <label className="block text-[12px] font-semibold">{text(language, 'கூறப்பட்ட குறள் எண்', 'Claimed Kural number')} <span className="font-normal text-muted-foreground">{text(language, '(விருப்பம்)', '(optional)')}</span><div className="relative mt-2"><input data-testid="input-claimed-id" type="number" min="1" max="1330" value={claimedId} onChange={(event) => setClaimedId(event.target.value)} placeholder={text(language, 'எ.கா. 391', 'e.g. 391')} className="h-11 w-full rounded-xl border border-input bg-background px-3 pr-10 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/15" /><ChevronDown className="pointer-events-none absolute right-3 top-3.5 rotate-[-90deg] text-muted-foreground" size={15} /></div>{kuralLookup.data && <span className="mt-2 block rounded-lg bg-muted px-3 py-2 font-normal text-muted-foreground" data-testid="text-claimed-kural-preview"><span className="font-tamil text-foreground">{kuralLookup.data.line1}</span><br /><span className="font-tamil text-foreground">{kuralLookup.data.line2}</span><br /><span className="font-data text-[9px]">{text(language, 'அதிகாரம்', 'Chapter')} {kuralLookup.data.chapter_no} · {kuralLookup.data.chapter_name}</span></span>}{kuralLookup.isError && <span className="mt-2 block text-[11px] font-normal text-muted-foreground" data-testid="error-kural-lookup">{text(language, 'குறள் தகவலைப் பெற முடியவில்லை.', 'Could not retrieve Kural details.')}</span>}</label>
          <button data-testid="button-verify-quote" type="submit" disabled={!quoteText.trim() || verify.isPending} className="flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-[13px] font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50">{verify.isPending ? <LoaderCircle className="animate-spin" size={16} /> : <FileSearch size={16} />}{verify.isPending ? text(language, 'சரிபார்க்கிறது…', 'Verifying…') : text(language, 'மேற்கோளைச் சரிபார்', 'Verify quotation')}<ArrowRight size={15} /></button>
        </div>
        {verify.isError && <InlineError message={text(language, 'இந்த நேரத்தில் மேற்கோளைச் சரிபார்க்க முடியவில்லை.', 'The quotation could not be checked just now.')} onRetry={() => verify.mutate({ data: { text: quoteText.trim(), ...(claimedId ? { claimed_id: Number(claimedId) } : {}) } })} />}
      </form>
    </section>
    {verify.data ? <VerificationResult result={verify.data} inputText={quoteText} /> : <section className="relative flex min-h-[310px] flex-col justify-between overflow-hidden rounded-[22px] border border-border bg-[#e9e4d8] p-6 sm:p-8">
      <div className="absolute -right-10 -top-16 h-64 w-64 rounded-full border border-primary/10" /><div className="absolute -right-1 -top-7 h-48 w-48 rounded-full border border-primary/10" />
      <div className="relative"><div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary"><CircleHelp size={19} /></div><p className="mt-5 font-display text-[21px] leading-7">{language === 'ta' ? <>முதலில் உரையைப் பார்ப்போம்,<br />கூறப்பட்ட எண்ணை அல்ல.</> : <>We check the text first,<br />not the claimed number.</>}</p><p className="mt-3 max-w-[290px] text-[13px] leading-6 text-foreground/65">{text(language, 'உங்கள் உரையை உள்ளூர் தொகுப்புடன் ஒப்பிட்டு, பொருந்தும் மற்றும் வேறுபடும் சொற்களைக் காட்டுகிறோம்.', 'We compare your text with the local corpus and show matching and differing words.')}</p></div>
      <div className="relative mt-8 flex items-center gap-3 border-l-2 border-primary/50 pl-4"><span className="h-10 w-10 rounded-full border border-primary/25 bg-primary/5" /><span className="h-px w-14 bg-primary/30" /><span className="h-6 w-6 rounded-full border border-primary/25 bg-primary/5" /><span className="h-px flex-1 bg-primary/30" /></div>
    </section>}
    <div className="flex items-start gap-3 rounded-xl border border-border/80 bg-secondary/50 px-4 py-3.5 lg:col-span-2"><Sparkles size={15} className="mt-0.5 shrink-0 text-primary" /><p className="text-[12px] leading-5 text-muted-foreground">{text(language, 'மெய்க்குறள் திருக்குறள் தொகுப்பில் மட்டுமே தேடுகிறது. உண்மைத்தன்மையைத் தீர்மானிக்க பெரிய மொழி மாதிரியைப் பயன்படுத்தாது. இங்கு கிடைக்காத மேற்கோள் வேறு நூலில் இருக்கலாம்.', 'Meikural searches only the Tirukkural corpus and does not use a large language model to judge authenticity. A quote not found here may appear in another work.')}</p></div>
  </div>;
}

function makeSamples(first: Kural, second: Kural) {
  const real = `${first.line1}\n${first.line2}`;
  const spliced = `${first.line1}\n${second.line2}`;
  const tokenize = (value: string) => value.split(/\s+/).filter(Boolean);
  const normalize = (word: string) => word.replace(/[.,;:!?()[\]{}"'“”‘’。，、]/g, '');
  const firstWords = new Set(tokenize(`${first.line1} ${first.line2}`).map(normalize));
  const replacementWord = tokenize(`${second.line1} ${second.line2}`).find((word) => {
    const clean = normalize(word);
    return clean.length > 1 && !firstWords.has(clean);
  });
  let replacement = '';
  if (replacementWord) {
    const lines = [first.line1, first.line2];
    const wordToReplace = tokenize(lines[0])[0];
    if (wordToReplace) {
      lines[0] = lines[0].replace(wordToReplace, replacementWord);
      replacement = lines.join('\n');
    }
  }
  return { real, spliced, replacement };
}

function VerificationResult({ result, inputText }: { result: Verification; inputText: string }) {
  return <div className="space-y-4">
    <StatusCard verdict={result.verdict} score={result.score} matchedId={result.matched_id} scope={result.matched_scope} claimedOk={result.claimed_id_ok} warning={result.warning} />
    {result.verdict === 'not_found' ? <Abstention /> : result.matched_kural ? <><KuralCard kural={result.matched_kural} diff={result.diff} /><DiffComparison diff={result.diff} inputText={inputText} /></> : null}
  </div>;
}

function StatusCard({ verdict, score, matchedId, scope, claimedOk, warning }: { verdict: string; score: number; matchedId: number | null; scope: string | null; claimedOk: boolean | null; warning: string | null }) {
  const { language } = useLanguage();
  const wordCountMismatch = warning === 'line_word_count_mismatch';
  const style = verdict === 'verified' ? 'status-verified' : verdict === 'near_match' ? 'status-near' : 'status-not-found';
  const title = wordCountMismatch ? text(language, 'வரி அமைப்பு பொருந்தவில்லை', 'Line structure mismatch') : verdict === 'verified' ? text(language, 'தொகுப்பில் உறுதிப்படுத்தப்பட்டது', 'Verified in corpus') : verdict === 'near_match' ? text(language, 'அருகிய பொருத்தம் — உரையை மீள்பார்க்கவும்', 'Near match — review the text') : text(language, 'தொகுப்பில் கிடைக்கவில்லை', 'Not found in corpus');
  const message = wordCountMismatch
    ? text(language, 'முதல் வரியில் 4 சொற்களும் இரண்டாம் வரியில் 3 சொற்களும் இருக்க வேண்டும்.', 'A full match requires 4 words on line 1 and 3 words on line 2.')
    : verdict === 'verified'
    ? text(language, 'இந்த உரை உள்ளூர் திருக்குறள் தொகுப்பிலுள்ள ஒரு குறளுடன் அப்படியே பொருந்துகிறது.', 'This text exactly matches a Kural in the local Tirukkural corpus.')
    : verdict === 'near_match'
      ? text(language, 'இதற்கு நெருக்கமான உரை கிடைத்துள்ளது; ஆனால் இது அப்படியே பொருந்தவில்லை.', 'A similar passage was found, but it is not an exact match.')
      : text(language, 'இந்தத் தொகுப்பில் பொருந்தும் குறள் கண்டறியப்படவில்லை.', 'No matching Kural was found in this corpus.');
  const scopeLabel = scope === 'line1' ? text(language, 'முதல் அடி', 'First line') : scope === 'line2' ? text(language, 'இரண்டாம் அடி', 'Second line') : scope === 'full' ? text(language, 'முழுக் குறள்', 'Full Kural') : null;
  const warningText = warning === 'attribution_mismatch'
    ? text(language, 'கூறப்பட்ட குறள் எண் பொருந்தவில்லை; உரை வேறொரு குறளுடன் பொருந்துகிறது.', 'The claimed Kural number does not match; the text matches another Kural.')
    : wordCountMismatch
      ? null
      : warning ? text(language, 'குறள் எண்ணை மீண்டும் சரிபார்க்கவும்.', 'Check the Kural number again.') : null;
  const marker = verdict === 'verified' ? <Check size={17} /> : verdict === 'near_match' ? <TriangleAlert size={17} /> : <FileSearch size={17} />;
  return <section className={`rounded-[20px] border p-5 ${style}`} data-testid={`status-${verdict}`}>
    <div className="flex items-start justify-between gap-4"><div className="flex items-start gap-3"><span className="mt-0.5">{marker}</span><div><h3 className="text-[15px] font-bold">{title}</h3><p className="mt-1 text-[12px] leading-5 opacity-80">{message}</p></div></div><span className="shrink-0 font-data text-[11px]">{Math.round(score)}%<span className="ml-1 opacity-60">{text(language, 'பொருத்தம்', 'match')}</span></span></div>
    <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 border-t border-current/15 pt-3 font-data text-[10px] uppercase tracking-[.08em] opacity-80">
      {matchedId !== null && <span>{text(language, 'நெருக்கமான பொருத்தம்: குறள்', 'Closest match: Kural')} {matchedId}</span>}{scopeLabel && <span>{text(language, 'பொருந்திய பகுதி:', 'Matched portion:')} {scopeLabel}</span>}{claimedOk !== null && <span>{text(language, 'கூறிய எண்', 'Claimed number')} {claimedOk ? text(language, 'பொருந்துகிறது', 'matches') : text(language, 'பொருந்தவில்லை', 'does not match')}</span>}
    </div>{warningText && <p className="mt-3 text-[12px] leading-5">{warningText}</p>}
  </section>;
}

function Abstention() {
  const { language } = useLanguage();
  return <div className="rounded-[20px] border border-[#d9b8a3] bg-[#f7eee6] p-5" data-testid="text-abstention"><div className="flex gap-3"><CircleHelp className="mt-0.5 shrink-0 text-[#98543f]" size={17} /><p className="text-[13px] leading-6 text-[#69483c]">{text(language, 'திருக்குறள் தொகுப்பில் இது காணப்படவில்லை. இதன் உண்மைத்தன்மையை உறுதிப்படுத்த முடியாது. தயவுசெய்து தமிழ் அறிஞரிடம் ஆலோசிக்கவும்.', 'This was not found in the Tirukkural corpus, so its authenticity cannot be confirmed. Please consult a Tamil scholar.')}</p></div></div>;
}

function KuralCard({ kural, diff }: { kural: Kural; diff?: Verification['diff'] }) {
  const { language } = useLanguage();
  return <section className="overflow-hidden rounded-[20px] border border-border bg-card" data-testid={`card-matched-kural-${kural.id}`}>
    <div className="flex items-center justify-between border-b border-border bg-muted/55 px-5 py-3"><div className="flex items-center gap-2 font-data text-[10px] uppercase tracking-[.13em] text-muted-foreground"><BookOpen size={14} className="text-primary" />{text(language, 'குறள்', 'Kural')} <span className="text-foreground">#{kural.id}</span><span>· {kural.paal}</span></div><span className="text-right text-[11px] text-muted-foreground">{text(language, 'அதிகாரம்', 'Chapter')} {kural.chapter_no} · {kural.chapter_name}</span></div>
    <div className="px-5 py-5 sm:px-6"><p className="font-tamil text-[17px] leading-[2.1] text-foreground" data-testid="text-kural-line1">{renderDiffLine(kural.line1, diff, 'corpus')}</p><p className="font-tamil text-[17px] leading-[2.1] text-foreground" data-testid="text-kural-line2">{renderDiffLine(kural.line2, diff, 'corpus')}</p>{kural.meaning_en && <details className="mt-4 border-t border-border pt-3 text-[12px] leading-5 text-muted-foreground" data-testid="text-kural-meaning"><summary className="cursor-pointer font-semibold">{text(language, 'மூலத்தில் உள்ள ஆங்கிலப் பொருளைக் காண்க', 'View the source English meaning')}</summary><p className="mt-2 italic">{kural.meaning_en}</p></details>}<div className="mt-4 flex items-center gap-2 font-data text-[9px] uppercase tracking-[.12em] text-muted-foreground"><span className={`h-1.5 w-1.5 rounded-full ${kural.needs_human_review ? 'bg-amber-500' : 'bg-primary'}`} />{kural.needs_human_review ? text(language, 'மனிதர் சரிபார்ப்பு பரிந்துரைக்கப்படுகிறது', 'Human review recommended') : text(language, 'தொகுப்பிலுள்ள பதிவு', 'Corpus entry')}</div></div>
  </section>;
}

function renderDiffLine(text: string, diff: Verification['diff'] | undefined, field: 'input' | 'corpus') {
  if (!diff?.length) return text;
  const fragments: ReactNode[] = [];
  let cursor = 0;
  diff.forEach((part, index) => {
    const token = part[field];
    if (!token) return;
    const position = text.indexOf(token, cursor);
    if (position < 0) return;
    if (position > cursor) fragments.push(text.slice(cursor, position));
    fragments.push(<mark key={`${index}-${position}`} className={part.kind === 'same' ? 'diff-same' : 'diff-changed'}>{text.slice(position, position + token.length)}</mark>);
    cursor = position + token.length;
  });
  if (!fragments.length) return text;
  if (cursor < text.length) fragments.push(text.slice(cursor));
  return fragments;
}

function DiffComparison({ diff, inputText }: { diff: Verification['diff']; inputText: string }) {
  const { language } = useLanguage();
  if (!diff.length) return null;
  return <section className="rounded-[18px] border border-border bg-card p-4 sm:p-5" data-testid="word-diff"><div className="mb-3 flex items-center justify-between"><h3 className="text-[12px] font-semibold">{text(language, 'சொல் ஒப்பீடு', 'Word comparison')}</h3><span className="font-data text-[9px] uppercase tracking-[.1em] text-muted-foreground">{text(language, 'உள்ளீடு / தொகுப்பு', 'Input / corpus')}</span></div><div className="grid grid-cols-2 gap-3 border-b border-border pb-2 font-data text-[9px] uppercase tracking-[.12em] text-muted-foreground"><span>{text(language, 'நீங்கள் அளித்த உரை', 'Your text')}</span><span>{text(language, 'தொகுப்பு உரை', 'Corpus text')}</span></div><div className="divide-y divide-border">{diff.map((part, index) => <div key={`${index}-${part.kind}`} className="grid grid-cols-2 gap-3 py-2.5 text-[12px] leading-5"><span className={part.kind === 'input_only' || part.kind === 'changed' ? 'rounded bg-[#f5e4dc] px-1 text-[#87513e]' : 'text-foreground'}>{part.input || <span className="text-muted-foreground/50">—</span>}</span><span className={part.kind === 'corpus_only' || part.kind === 'changed' ? 'rounded bg-[#e7f0e9] px-1 text-[#285b49]' : 'text-foreground'}>{part.corpus || <span className="text-muted-foreground/50">—</span>}</span></div>)}</div><p className="mt-2 border-t border-border pt-3 text-[10px] leading-4 text-muted-foreground">{text(language, 'நீங்கள் உள்ளிட்டது:', 'You entered:')} {inputText}</p></section>;
}

function GuardPanel() {
  const { language } = useLanguage();
  const [answer, setAnswer] = useState('');
  const guard = useGuardAnswer();
  const submit = (event: FormEvent) => { event.preventDefault(); if (answer.trim()) guard.mutate({ data: { llm_answer: answer.trim() } }); };
  return <div className="space-y-6">
    <section className="rounded-[22px] border border-border bg-card p-5 shadow-[0_8px_32px_hsl(36_26%_45%/.05)] sm:p-7">
      <div className="flex items-start justify-between gap-4"><div><p className="font-data text-[10px] uppercase tracking-[.18em] text-muted-foreground">{text(language, '02 / பதில் ஆய்வு', '02 / Answer review')}</p><h2 className="mt-2 font-display text-[24px] tracking-[-.02em]">{text(language, 'ஒரு பதிலைச் சரிபார்க்கவும்', 'Review an answer')}</h2><p className="mt-2 max-w-[500px] text-[13px] leading-6 text-muted-foreground">{text(language, 'சாட்பாட்டின் பதிலை ஒட்டவும். அசல் சொற்களை மாற்றாமல், அதிலுள்ள மேற்கோள்களைக் கண்டறிந்து குறிக்கிறோம்.', 'Paste a chatbot response. We find and annotate quotations without changing the original wording.')}</p></div><div className="hidden h-10 w-10 items-center justify-center rounded-full bg-secondary text-primary sm:flex"><ScanText size={19} /></div></div>
      <form onSubmit={submit} className="mt-6"><label htmlFor="answer-input" className="mb-2 block text-[12px] font-semibold">{text(language, 'சாட்பாட் பதில்', 'Chatbot answer')}</label><textarea id="answer-input" data-testid="input-guard-answer" value={answer} onChange={(event) => setAnswer(event.target.value)} maxLength={20000} placeholder={text(language, 'முழுப் பதிலையும் இங்கே ஒட்டவும்…', 'Paste the complete answer here…')} className="min-h-[188px] w-full resize-y rounded-xl border border-input bg-background px-4 py-3.5 text-[14px] leading-7 outline-none placeholder:text-muted-foreground/60 focus:border-primary focus:ring-2 focus:ring-primary/15" /><div className="mt-3 flex flex-wrap items-center justify-between gap-3"><span className="font-data text-[10px] text-muted-foreground">{answer.length.toLocaleString()} / 20,000 {text(language, 'எழுத்துகள்', 'characters')}</span><button data-testid="button-guard-answer" type="submit" disabled={!answer.trim() || guard.isPending} className="flex h-11 items-center gap-2 rounded-xl bg-primary px-5 text-[13px] font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50">{guard.isPending ? <LoaderCircle className="animate-spin" size={16} /> : <ShieldCheck size={16} />}{guard.isPending ? text(language, 'ஆய்வு செய்கிறது…', 'Reviewing…') : text(language, 'பதிலை ஆய்வு செய்', 'Review answer')}<ArrowRight size={15} /></button></div>
        {guard.isError && <InlineError message={text(language, 'இந்த நேரத்தில் பதிலை ஆய்வு செய்ய முடியவில்லை.', 'The answer could not be reviewed just now.')} onRetry={() => guard.mutate({ data: { llm_answer: answer.trim() } })} />}
      </form>
    </section>
    {guard.data ? <GuardOutput result={guard.data} /> : <div className="flex gap-3 rounded-xl border border-border bg-muted/45 px-4 py-3.5"><CircleHelp className="mt-0.5 shrink-0 text-primary" size={15} /><p className="text-[12px] leading-5 text-muted-foreground">{text(language, 'குறிப்புகளைத் தொகுப்பு சரிபார்ப்புக் கருவி வழங்குகிறது. API வழங்கிய குறியீடுகள் அப்படியே பாதுகாக்கப்படும்.', 'Annotations come from the corpus checker. Markers are preserved exactly as returned by the API.')}</p></div>}
  </div>;
}

function GuardOutput({ result }: { result: { annotated_answer: string; quotes: GuardQuote[]; summary: { verified: number; near: number; not_found: number } } }) {
  const { language } = useLanguage();
  const [copied, setCopied] = useState(false);
  const copy = async () => { try { await navigator.clipboard.writeText(result.annotated_answer); setCopied(true); window.setTimeout(() => setCopied(false), 1800); } catch { setCopied(false); } };
  return <div className="space-y-5">
    <div className="grid grid-cols-3 gap-2 sm:gap-3">
      <CountCard label={text(language, 'உறுதி செய்யப்பட்டது', 'Verified')} count={result.summary.verified} kind="verified" />
      <CountCard label={text(language, 'அருகிய பொருத்தம்', 'Near match')} count={result.summary.near} kind="near" />
      <CountCard label={text(language, 'கிடைக்கவில்லை', 'Not found')} count={result.summary.not_found} kind="not-found" />
    </div>
    <section className="overflow-hidden rounded-[20px] border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3.5"><div><p className="font-data text-[10px] uppercase tracking-[.16em] text-muted-foreground">{text(language, 'குறிப்பிடப்பட்ட பதில்', 'Annotated response')}</p><p className="mt-1 text-[11px] text-muted-foreground">{text(language, 'அசல் API வெளியீடு · குறியீடுகள் பாதுகாக்கப்பட்டன', 'Original API output · markers preserved')}</p></div><button onClick={copy} data-testid="button-copy-annotation" className="flex h-9 items-center gap-2 rounded-lg border border-border px-3 text-[11px] font-semibold hover:bg-muted">{copied ? <Check size={14} /> : <Clipboard size={14} />}{copied ? text(language, 'நகலெடுக்கப்பட்டது', 'Copied') : text(language, 'குறிப்பிட்ட உரையை நகலெடு', 'Copy annotated text')}</button></div>
      <pre className="whitespace-pre-wrap break-words px-5 py-5 font-sans text-[13px] leading-7 text-foreground" data-testid="text-annotated-answer">{result.annotated_answer}</pre>
    </section>
    <section><div className="mb-3 flex items-center justify-between"><h3 className="font-display text-[19px]">{text(language, 'கண்டறியப்பட்ட மேற்கோள்கள்', 'Detected quotations')}</h3><span className="font-data text-[10px] text-muted-foreground">{result.quotes.length} {text(language, result.quotes.length === 1 ? 'மேற்கோள்' : 'மேற்கோள்கள்', result.quotes.length === 1 ? 'quote' : 'quotes')}</span></div>{result.quotes.length ? <div className="space-y-3">{result.quotes.map((quote, index) => <QuoteReview key={`${quote.matched_id ?? 'none'}-${index}`} quote={quote} index={index} />)}</div> : <div className="rounded-2xl border border-dashed border-border bg-card px-5 py-8 text-center"><div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-secondary text-primary"><ScanText size={18} /></div><p className="mt-3 text-sm font-semibold">{text(language, 'மேற்கோள்கள் எதுவும் கண்டறியப்படவில்லை', 'No quotations detected')}</p><p className="mt-1 text-xs text-muted-foreground">{text(language, 'சரிபார்க்க வேண்டிய மேற்கோள் இந்தப் பதிலில் இல்லை.', 'The response did not contain a quotation to check.')}</p></div>}</section>
  </div>;
}

function CountCard({ label, count, kind }: { label: string; count: number; kind: string }) {
  return <div className={`rounded-xl border px-3 py-3 sm:px-4 ${kind === 'verified' ? 'count-verified' : kind === 'near' ? 'count-near' : 'count-not-found'}`} data-testid={`count-${kind}`}><p className="font-data text-[9px] uppercase tracking-[.1em] opacity-75 sm:text-[10px]">{label}</p><p className="mt-1 font-display text-[26px] leading-8">{count}</p></div>;
}

function QuoteReview({ quote, index }: { quote: GuardQuote; index: number }) {
  const { language } = useLanguage();
  const scope = quote.matched_scope === 'line1' ? text(language, 'முதல் அடி', 'First line') : quote.matched_scope === 'line2' ? text(language, 'இரண்டாம் அடி', 'Second line') : quote.matched_scope === 'full' ? text(language, 'முழுக் குறள்', 'Full Kural') : quote.matched_scope;
  return <article className="rounded-[18px] border border-border bg-card p-4 sm:p-5" data-testid={`card-guard-quote-${index}`}>
    <div className="flex items-start justify-between gap-3"><blockquote className="line-clamp-4 text-[13px] leading-6 text-foreground/85">“{quote.text}”</blockquote><span className={`shrink-0 rounded-full px-2.5 py-1 font-data text-[9px] uppercase tracking-[.08em] ${quote.verdict === 'verified' ? 'pill-verified' : quote.verdict === 'near_match' ? 'pill-near' : 'pill-not-found'}`}>{quote.warning === 'line_word_count_mismatch' ? text(language, 'வரி அமைப்பு பொருந்தவில்லை', 'Structure mismatch') : quote.verdict === 'near_match' ? text(language, 'அருகிய பொருத்தம்', 'Near match') : quote.verdict === 'not_found' ? text(language, 'கிடைக்கவில்லை', 'Not found') : text(language, 'உறுதி செய்யப்பட்டது', 'Verified')}</span></div>
    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-data text-[10px] text-muted-foreground">{quote.matched_id !== null && <span>{text(language, 'நெருக்கமான குறள்', 'Closest Kural')} {quote.matched_id}</span>}<span>{Math.round(quote.score)}% {text(language, 'மதிப்பெண்', 'score')}</span>{scope && <span>{scope}</span>}</div>
    {quote.verdict === 'not_found' ? <p className="mt-3 text-[11px] leading-5 text-[#845340]">{text(language, 'திருக்குறள் தொகுப்பில் இது கிடைக்கவில்லை. இதன் உண்மைத்தன்மையை உறுதிப்படுத்த முடியாது. தமிழ் அறிஞரிடம் ஆலோசிக்கவும்.', 'Not found in the Tirukkural corpus. This cannot be confirmed as authentic. Please consult a Tamil scholar.')}</p> : quote.matched_kural && <div className="mt-3 rounded-xl bg-muted/65 px-4 py-3"><p className="font-tamil text-[14px] leading-8">{quote.matched_kural.line1}<br />{quote.matched_kural.line2}</p><p className="mt-1 font-data text-[9px] text-muted-foreground">{text(language, 'குறள்', 'Kural')} {quote.matched_kural.id} · {quote.matched_kural.chapter_name}</p></div>}
    {quote.warning && <p className="mt-3 text-[11px] leading-5 text-muted-foreground">{quote.warning === 'attribution_mismatch' ? text(language, 'கூறப்பட்ட குறள் எண் பொருந்தவில்லை.', 'The claimed Kural number does not match.') : quote.warning === 'line_word_count_mismatch' ? text(language, 'முழுப் பொருத்தத்திற்கு முதல் வரியில் 4 சொற்களும் இரண்டாம் வரியில் 3 சொற்களும் இருக்க வேண்டும்.', 'A full match requires 4 words on line 1 and 3 words on line 2.') : quote.warning}</p>}
  </article>;
}

function EvaluationPanel() {
  const { language } = useLanguage();
  const query = useGetEvaluationResults({ query: { queryKey: getGetEvaluationResultsQueryKey() } });
  if (query.isLoading) return <EvaluationSkeleton />;
  if (query.isError) return <ErrorState message={text(language, 'மதிப்பீட்டு முடிவுகள் இப்போது கிடைக்கவில்லை.', 'Evaluation results are not available right now.')} onRetry={() => query.refetch()} />;
  if (!query.data) return <EmptyState title={text(language, 'மதிப்பீட்டு முடிவுகள் இல்லை', 'No evaluation results')} description={text(language, 'தொகுப்பிலிருந்து மதிப்பீட்டு அறிக்கை கிடைக்கவில்லை.', 'The corpus has not returned an evaluation report.')} />;
  return <EvaluationReport results={query.data} />;
}

function EvaluationReport({ results }: { results: EvaluationResults }) {
  const { language } = useLanguage();
  const metrics = [
    { key: 'verified_precision', label: text(language, 'உறுதிப்படுத்தலின் துல்லியம்', 'Verified precision'), value: results.metrics.verified_precision, note: text(language, 'உறுதி செய்யப்பட்ட முடிவுகளில் சரியானவை', 'How often a verified result is correct'), tone: 'primary' },
    { key: 'real_recall', label: text(language, 'உண்மையான மேற்கோள் மீட்பு', 'Real-quote recall'), value: results.metrics.real_recall, note: text(language, 'தொகுப்பிலுள்ள அறியப்பட்ட மேற்கோள்கள் மீட்கப்பட்டவை', 'Known corpus quotes recovered'), tone: 'gold' },
    { key: 'false_accept_rate', label: text(language, 'தவறான ஏற்பு விகிதம்', 'False accept rate'), value: results.metrics.false_accept_rate, note: text(language, 'பொருந்தாத உரை உறுதியானதாகக் குறிக்கப்பட்டது', 'Unmatched text marked verified'), tone: 'rust' },
    { key: 'tricky_near_match_rate', label: text(language, 'சிக்கலான அருகிய பொருத்தங்கள்', 'Tricky near matches'), value: results.metrics.tricky_near_match_rate, note: text(language, 'மதிப்பாய்வுக்காக வைக்கப்பட்ட கடினமான வேறுபாடுகள்', 'Hard variations kept for review'), tone: 'blue' },
    { key: 'fake_abstain_rate', label: text(language, 'உறுதியளிக்காத விகிதம்', 'Abstention rate'), value: results.metrics.fake_abstain_rate, note: text(language, 'உறுதிப்படுத்தப்படாத உரைக்கு மிகையான கூற்று இல்லை', 'Unconfirmed text not overclaimed'), tone: 'violet' },
  ];
  const sampleRows = Object.entries(results.metrics.sample_counts);
  return <div className="space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="font-data text-[10px] uppercase tracking-[.18em] text-muted-foreground">{text(language, '03 / மதிப்பீட்டு அறிக்கை', '03 / Evaluation report')}</p><h2 className="mt-2 font-display text-[26px] tracking-[-.02em]">{text(language, 'சரிபார்ப்புக் கருவி எவ்வளவு கவனமாகச் செயல்படுகிறது?', 'How careful is the checker?')}</h2><p className="mt-2 max-w-xl text-[13px] leading-6 text-muted-foreground">{text(language, 'திட்டத்தின் தரவுத்தொகுப்பின் அடிப்படையிலான நிர்ணய மதிப்பீடு. அளவீடுகள் பொருத்தச் செயல்பாட்டைக் குறிக்கின்றன; இலக்கிய அதிகாரத்தை அல்ல.', 'Deterministic evaluation against the project dataset. Metrics describe matching behavior, not literary authority.')}</p></div><div className="rounded-xl border border-border bg-card px-4 py-2.5"><p className="font-data text-[9px] uppercase tracking-[.12em] text-muted-foreground">{text(language, 'அருகிய பொருத்த வரம்பு', 'Near-match threshold')}</p><p className="mt-1 font-data text-[15px] text-primary">{results.near_threshold}<span className="text-[10px]">%</span></p></div></div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{metrics.map(({ key, ...metric }) => <MetricCard key={key} {...metric} />)}</div>
    <section className="rounded-[20px] border border-border bg-card p-5 sm:p-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-display text-[19px]">{text(language, 'வரம்பு மாற்ற மதிப்பீடு', 'Threshold sweep')}</h3><p className="mt-1 text-[11px] text-muted-foreground">{text(language, 'அருகிய பொருத்த வரம்பு மாறும்போது ஏற்படும் சமநிலைகள்', 'Trade-offs as the near-match threshold changes')}</p></div><div className="flex flex-wrap gap-x-4 gap-y-2 text-[10px]"><Legend color="#275b4b" label={text(language, 'உண்மையான மேற்கோள் மீட்பு', 'Real recall')} /><Legend color="#b75e45" label={text(language, 'தவறான ஏற்பு', 'False accept')} /><Legend color="#c89c48" label={text(language, 'சிக்கலான அருகிய பொருத்தம்', 'Tricky near match')} /></div></div>
      {results.threshold_sweep.length ? <div className="mt-6 h-[260px] w-full" data-testid="chart-threshold-sweep"><ResponsiveContainer width="100%" height="100%"><LineChart data={results.threshold_sweep} margin={{ top: 5, right: 10, left: -18, bottom: 0 }}><CartesianGrid stroke="hsl(39 20% 83%)" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="threshold" tickFormatter={(value: number) => `${Math.round(value)}%`} tickLine={false} axisLine={false} tick={{ fill: 'hsl(163 10% 44%)', fontSize: 10 }} dy={9} /><YAxis domain={[0, 1]} tickFormatter={(value: number) => `${Math.round(value * 100)}%`} tickLine={false} axisLine={false} tick={{ fill: 'hsl(163 10% 44%)', fontSize: 10 }} /><ChartTooltip content={<SweepTooltip />} /><Line type="monotone" dataKey="real_recall" name={text(language, 'உண்மையான மேற்கோள் மீட்பு', 'Real recall')} stroke="#275b4b" strokeWidth={2.5} dot={{ r: 3, fill: '#275b4b', strokeWidth: 0 }} activeDot={{ r: 5 }} /><Line type="monotone" dataKey="false_accept_rate" name={text(language, 'தவறான ஏற்பு', 'False accept')} stroke="#b75e45" strokeWidth={2} dot={{ r: 2.5, fill: '#b75e45', strokeWidth: 0 }} /><Line type="monotone" dataKey="tricky_near_match_rate" name={text(language, 'சிக்கலான அருகிய பொருத்தம்', 'Tricky near match')} stroke="#c89c48" strokeWidth={2} dot={{ r: 2.5, fill: '#c89c48', strokeWidth: 0 }} /></LineChart></ResponsiveContainer></div> : <EmptyState title={text(language, 'வரம்பு புள்ளிகள் இல்லை', 'No threshold points')} description={text(language, 'மதிப்பீட்டு அறிக்கையில் வரம்பு தரவு இல்லை.', 'The evaluation report contains no sweep data.')} />}</section>
    <section className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
      <div className="rounded-[20px] border border-border bg-card p-5 sm:p-6"><h3 className="font-display text-[19px]">{text(language, 'முடிவு வகைப் பகிர்வு', 'Verdict distribution')}</h3><p className="mt-1 text-[11px] text-muted-foreground">{text(language, 'இந்த மதிப்பீட்டில் பதிவான முடிவுகள்', 'Results recorded in this evaluation')}</p><div className="mt-5 space-y-4">{Object.entries(results.verdict_counts).map(([label, value]) => <DistributionRow key={label} label={label} value={value} total={Object.values(results.verdict_counts).reduce((sum, n) => sum + n, 0)} />)}</div></div>
      <div className="rounded-[20px] border border-border bg-card p-5 sm:p-6"><h3 className="font-display text-[19px]">{text(language, 'தரவுத்தொகுப்பு மற்றும் மாதிரி எண்ணிக்கைகள்', 'Dataset & sample counts')}</h3><p className="mt-1 text-[11px] text-muted-foreground">{text(language, 'API அறிக்கையின்படி மதிப்பீட்டின் உள்ளடக்கம்', 'Evaluation coverage, as reported by the API')}</p><div className="mt-4 divide-y divide-border">{Object.entries(results.dataset_counts).map(([label, value]) => <div key={label} className="flex items-center justify-between gap-3 py-2.5 text-[12px]"><span className="capitalize text-muted-foreground">{humanize(label, language)}</span><span className="font-data text-[12px]">{value.toLocaleString()}</span></div>)}</div>{sampleRows.length > 0 && <div className="mt-3 border-t border-border pt-2">{sampleRows.map(([label, value]) => <div key={label} className="flex items-center justify-between gap-3 py-2 text-[11px]"><span className="capitalize text-muted-foreground">{humanize(label, language)} {text(language, 'மாதிரிகள்', 'samples')}</span><span className="font-data">{value.toLocaleString()}</span></div>)}</div>}</div>
    </section>
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4 font-data text-[10px] text-muted-foreground"><span>{text(language, 'அறிக்கை உருவாக்கப்பட்ட நேரம்', 'Report generated')} {formatDate(results.generated_at, language)}</span><span>{text(language, 'வரம்புகள் பரிசோதனைக்குரியவை · மனித மதிப்பீடு அவசியம்', 'Thresholds are experimental · human judgment remains essential')}</span></div>
  </div>;
}

function MetricCard({ label, value, note, tone }: { label: string; value: number; note: string; tone: string }) {
  return <article className={`metric-card rounded-[17px] border border-border bg-card p-4 ${tone}`} data-testid={`metric-${tone}`}><div className="flex items-start justify-between gap-2"><p className="text-[12px] font-semibold leading-5">{label}</p><Activity size={14} className="mt-0.5 opacity-60" /></div><p className="mt-3 font-display text-[30px] leading-8 tracking-[-.04em]">{(value * 100).toFixed(1)}<span className="ml-0.5 text-[15px]">%</span></p><p className="mt-2 text-[10px] leading-4 text-muted-foreground">{note}</p></article>;
}

function Legend({ color, label }: { color: string; label: string }) { return <span className="flex items-center gap-1.5 text-muted-foreground"><i className="h-2 w-2 rounded-full" style={{ background: color }} />{label}</span>; }

function SweepTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: number }) {
  const { language } = useLanguage();
  if (!active || !payload?.length) return null;
  return <div className="rounded-xl border border-border bg-card p-3 shadow-lg"><p className="mb-2 font-data text-[10px] text-muted-foreground">{text(language, 'வரம்பு', 'Threshold')} {(label ?? 0).toFixed(1)}%</p>{payload.map((item) => <p key={item.name} className="mt-1 flex items-center justify-between gap-5 text-[11px]"><span style={{ color: item.color }}>{item.name}</span><span className="font-data">{(item.value * 100).toFixed(1)}%</span></p>)}</div>;
}

function DistributionRow({ label, value, total }: { label: string; value: number; total: number }) {
  const { language } = useLanguage();
  const percentage = total ? value / total * 100 : 0;
  const kind = label === 'verified' ? 'fill-verified' : label === 'near_match' ? 'fill-near' : 'fill-not-found';
  return <div data-testid={`distribution-${label}`}><div className="mb-1.5 flex justify-between text-[11px]"><span className="capitalize text-muted-foreground">{humanize(label, language)}</span><span className="font-data">{value.toLocaleString()} <span className="text-muted-foreground">· {percentage.toFixed(1)}%</span></span></div><div className="h-2 overflow-hidden rounded-full bg-muted"><div className={`h-full rounded-full ${kind}`} style={{ width: `${percentage}%` }} /></div></div>;
}

function humanize(value: string, language: Language) {
  const labels: Record<string, Record<Language, string>> = {
    verified: { ta: 'உறுதி செய்யப்பட்டது', en: 'Verified' },
    near_match: { ta: 'அருகிய பொருத்தம்', en: 'Near match' },
    not_found: { ta: 'கிடைக்கவில்லை', en: 'Not found' },
    real_exact: { ta: 'அசல் மேற்கோள்கள்', en: 'Exact real quotes' },
    real_typo: { ta: 'எழுத்துப் பிழையுள்ள மேற்கோள்கள்', en: 'Quotes with typos' },
    tricky: { ta: 'சிக்கலான வேறுபாடுகள்', en: 'Tricky variations' },
    fake: { ta: 'புனையப்பட்ட மேற்கோள்கள்', en: 'Fabricated quotes' },
    real_quotes: { ta: 'உண்மையான மேற்கோள்கள்', en: 'Real quotes' },
    altered_quotes: { ta: 'மாற்றப்பட்ட மேற்கோள்கள்', en: 'Altered quotes' },
    fabricated_quotes: { ta: 'புனையப்பட்ட மேற்கோள்கள்', en: 'Fabricated quotes' },
  };
  return labels[value]?.[language] ?? value.replaceAll('_', ' ');
}
function formatDate(value: string, language: Language) { const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString(language === 'ta' ? 'ta-IN' : 'en-US', { dateStyle: 'medium', timeStyle: 'short' }); }

function InlineError({ message, onRetry }: { message: string; onRetry: () => void }) {
  const { language } = useLanguage();
  return <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/25 bg-destructive/5 px-3.5 py-3" role="alert" data-testid="error-mutation"><p className="text-[12px] leading-5 text-destructive">{message}</p><button type="button" onClick={onRetry} className="flex items-center gap-1.5 text-[11px] font-semibold text-destructive" data-testid="button-retry-mutation"><RefreshCw size={13} />{text(language, 'மீண்டும் முயற்சி', 'Retry')}</button></div>;
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  const { language } = useLanguage();
  return <div className="rounded-[22px] border border-destructive/25 bg-card px-6 py-12 text-center" role="alert" data-testid="error-evaluation"><div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-destructive/10 text-destructive"><TriangleAlert size={19} /></div><h2 className="mt-4 font-display text-[20px]">{text(language, 'அறிக்கையை ஏற்ற முடியவில்லை', 'Unable to load report')}</h2><p className="mt-2 text-[13px] text-muted-foreground">{message}</p><button onClick={onRetry} className="mx-auto mt-5 flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-[12px] font-semibold text-primary-foreground" data-testid="button-retry-evaluation"><RefreshCw size={14} />{text(language, 'மீண்டும் முயற்சி', 'Try again')}</button></div>;
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="rounded-xl border border-dashed border-border px-5 py-10 text-center" data-testid="empty-evaluation"><p className="font-display text-[18px]">{title}</p><p className="mt-1 text-[12px] text-muted-foreground">{description}</p></div>;
}

function EvaluationSkeleton() {
  const { language } = useLanguage();
  return <div className="space-y-6" aria-label={text(language, 'மதிப்பீட்டு முடிவுகள் ஏற்றப்படுகின்றன', 'Loading evaluation results')} data-testid="loading-evaluation"><div className="h-20 animate-pulse rounded-2xl bg-muted" /><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{[1, 2, 3, 4, 5].map((item) => <div key={item} className="h-32 animate-pulse rounded-2xl bg-muted" />)}</div><div className="h-[300px] animate-pulse rounded-2xl bg-muted" /></div>;
}

function Router() {
  const { language } = useLanguage();
  return <RoutedErrorBoundary><Switch><Route path="/" component={Home} /><Route component={() => <NotFound language={language} />} /></Switch></RoutedErrorBoundary>;
}

function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

function App() {
  const [language, setLanguage] = useState<Language>(() => localStorage.getItem('kuralguard-language') === 'en' ? 'en' : 'ta');
  useEffect(() => {
    localStorage.setItem('kuralguard-language', language);
    document.documentElement.lang = language;
    const title = text(language, 'மெய்க்குறள்', 'Meikural');
    document.title = title;
    document.querySelectorAll<HTMLMetaElement>('meta[property="og:title"], meta[name="twitter:title"]').forEach((meta) => { meta.content = title; });
    const description = text(language, 'திருக்குறள் தொகுப்புடன் மேற்கோள்களை ஒப்பிட்டு சரிபார்க்கும் கருவி.', 'Verify quotations against the Tirukkural corpus.');
    document.querySelectorAll<HTMLMetaElement>('meta[name="description"], meta[property="og:description"], meta[name="twitter:description"]').forEach((meta) => { meta.content = description; });
  }, [language]);
  return <LanguageContext.Provider value={{ language, setLanguage }}><QueryClientProvider client={queryClient}><TooltipProvider><WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}><Router /></WouterRouter><Toaster /></TooltipProvider></QueryClientProvider></LanguageContext.Provider>;
}

export default App;
