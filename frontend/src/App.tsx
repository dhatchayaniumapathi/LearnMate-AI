import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard,
  Bot,
  Files,
  BookOpen,
  HelpCircle,
  Layers,
  Calendar,
  BarChart3,
  Settings,
  Bell,
  Search,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  Clock,
  Flame,
  Brain,
  ChevronRight,
  ExternalLink,
  Activity,
  Menu,
  X
} from 'lucide-react';

interface NavItem {
  id: string;
  name: string;
  icon: React.ElementType;
  badge?: string;
  description: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', name: 'Dashboard', icon: LayoutDashboard, description: 'Overview and study progress' },
  { id: 'tutor', name: 'AI Study Tutor', icon: Bot, badge: 'Socratic', description: 'Conversational tutor with memory' },
  { id: 'documents', name: 'Document Hub & RAG', icon: Files, badge: 'Multimodal', description: 'Query slides, PDFs & notes' },
  { id: 'notes', name: 'Notes & Summaries', icon: BookOpen, description: 'AI Cornell notes & cheat sheets' },
  { id: 'quizzes', name: 'Quizzes & Mock Tests', icon: HelpCircle, badge: 'Adaptive', description: 'Practice exams with rationale' },
  { id: 'flashcards', name: 'Flashcard Decks', icon: Layers, description: 'Spaced repetition (SM-2) decks' },
  { id: 'planner', name: 'Smart Study Planner', icon: Calendar, description: 'Exam timetables & revision queue' },
  { id: 'analytics', name: 'Performance Analytics', icon: BarChart3, description: 'Mastery scores and weak areas' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);
  const [apiHealth, setApiHealth] = useState<{ status: string; version?: string } | null>(null);

  // Poll local API health check if backend is running
  useEffect(() => {
    fetch('http://localhost:8000/api/v1/health')
      .then((res) => res.json())
      .then((data) => setApiHealth({ status: data.status, version: data.version }))
      .catch(() => setApiHealth({ status: 'standby' }));
  }, []);

  const activeItem = NAV_ITEMS.find((item) => item.id === activeTab) || NAV_ITEMS[0];

  return (
    <div className="flex h-screen bg-slate-50 text-slate-800 font-sans overflow-hidden">
      {/* Mobile Backdrop */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar Navigation */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-72 bg-white border-r border-slate-200 flex flex-col transition-transform duration-200 ease-in-out lg:static lg:translate-x-0 ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Header */}
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-brand-500/20">
              <Brain className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg tracking-tight text-slate-900">LearnMate</span>
                <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-brand-50 text-brand-600 border border-brand-200">
                  AI
                </span>
              </div>
              <p className="text-xs text-slate-400">Personalized Learning OS</p>
            </div>
          </div>
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="lg:hidden text-slate-400 hover:text-slate-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
          <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            Core Modules
          </div>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  setMobileMenuOpen(false);
                }}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-brand-50 text-brand-700 shadow-sm font-semibold'
                    : 'text-slate-600 hover:bg-slate-100/70 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon
                    className={`h-4.5 w-4.5 ${
                      isActive ? 'text-brand-600' : 'text-slate-400 group-hover:text-slate-600'
                    }`}
                  />
                  <span>{item.name}</span>
                </div>
                {item.badge && (
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                      isActive
                        ? 'bg-brand-200/60 text-brand-800'
                        : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* User Card & Settings */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/50">
          <div className="flex items-center justify-between p-2 rounded-xl hover:bg-white transition-colors cursor-pointer border border-transparent hover:border-slate-200">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 text-white font-semibold text-sm flex items-center justify-center shadow-sm">
                AS
              </div>
              <div className="text-left">
                <p className="text-xs font-semibold text-slate-800">Alex Student</p>
                <p className="text-[11px] text-slate-400">alex@university.edu</p>
              </div>
            </div>
            <Settings className="h-4 w-4 text-slate-400 hover:text-slate-600" />
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Navbar */}
        <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden text-slate-600 hover:text-slate-900"
            >
              <Menu className="h-6 w-6" />
            </button>
            <div>
              <h1 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
                {activeItem.name}
              </h1>
              <p className="text-xs text-slate-400 hidden sm:block">
                {activeItem.description}
              </p>
            </div>
          </div>

          {/* Quick Actions & Status */}
          <div className="flex items-center gap-3">
            {/* Search Input */}
            <div className="relative hidden md:block">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search lectures, notes, concepts..."
                className="pl-9 pr-4 py-1.5 text-xs rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all w-64"
              />
            </div>

            {/* Backend Connectivity Status Pill */}
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-slate-200 bg-slate-50 text-xs">
              <span
                className={`h-2 w-2 rounded-full ${
                  apiHealth?.status === 'ok'
                    ? 'bg-emerald-500 ring-2 ring-emerald-200'
                    : 'bg-amber-400 ring-2 ring-amber-100'
                }`}
              />
              <span className="text-[11px] font-medium text-slate-600 hidden sm:inline">
                {apiHealth?.status === 'ok'
                  ? `API Online (${apiHealth.version || 'v0.1.0'})`
                  : 'FastAPI Standby'}
              </span>
            </div>

            <button className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors relative">
              <Bell className="h-4.5 w-4.5" />
              <span className="absolute top-1.5 right-1.5 h-2 w-2 bg-brand-500 rounded-full" />
            </button>
          </div>
        </header>

        {/* Scrollable View Container */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8 space-y-6">
          {/* Welcome Banner */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-brand-600 via-indigo-600 to-indigo-800 p-6 md:p-8 text-white shadow-lg shadow-brand-500/10">
            <div className="relative z-10 max-w-2xl">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur-md text-xs font-medium text-brand-100 mb-3 border border-white/10">
                <Sparkles className="h-3.5 w-3.5 text-amber-300" />
                Adaptive Learning Initialized
              </div>
              <h2 className="text-2xl md:text-3xl font-extrabold tracking-tight">
                Welcome to LearnMate AI
              </h2>
              <p className="mt-2 text-sm text-brand-100 leading-relaxed">
                Your intelligent study companion. Connect your lecture slides, ask Socratic questions, generate custom quizzes, and master complex concepts with spaced repetition.
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  onClick={() => setActiveTab('tutor')}
                  className="px-4 py-2 bg-white text-brand-700 hover:bg-brand-50 rounded-xl text-xs font-bold transition-all shadow-sm flex items-center gap-2"
                >
                  <Bot className="h-4 w-4" />
                  Start AI Tutor Session
                </button>
                <button
                  onClick={() => setActiveTab('documents')}
                  className="px-4 py-2 bg-brand-500/30 hover:bg-brand-500/40 border border-white/20 text-white rounded-xl text-xs font-semibold transition-all flex items-center gap-2"
                >
                  <Files className="h-4 w-4" />
                  Upload Course Materials
                </button>
              </div>
            </div>

            {/* Decorative background circle */}
            <div className="absolute -right-12 -bottom-12 w-64 h-64 rounded-full bg-white/5 pointer-events-none" />
          </div>

          {/* Metric Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-400">Current Study Streak</p>
                <p className="text-2xl font-bold text-slate-800 mt-1">4 Days</p>
                <span className="text-[11px] text-amber-600 font-medium flex items-center gap-1 mt-1">
                  <Flame className="h-3 w-3 fill-amber-500" /> Keep it going!
                </span>
              </div>
              <div className="h-12 w-12 rounded-xl bg-amber-50 text-amber-500 flex items-center justify-center">
                <Flame className="h-6 w-6" />
              </div>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-400">Concept Mastery</p>
                <p className="text-2xl font-bold text-slate-800 mt-1">78%</p>
                <span className="text-[11px] text-emerald-600 font-medium flex items-center gap-1 mt-1">
                  <CheckCircle2 className="h-3 w-3" /> +4% this week
                </span>
              </div>
              <div className="h-12 w-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
                <Activity className="h-6 w-6" />
              </div>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-400">SRS Cards Due</p>
                <p className="text-2xl font-bold text-slate-800 mt-1">18 Cards</p>
                <span className="text-[11px] text-indigo-600 font-medium flex items-center gap-1 mt-1">
                  <Clock className="h-3 w-3" /> 2 decks ready
                </span>
              </div>
              <div className="h-12 w-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                <Layers className="h-6 w-6" />
              </div>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-400">Indexed Course Docs</p>
                <p className="text-2xl font-bold text-slate-800 mt-1">6 Files</p>
                <span className="text-[11px] text-slate-400 font-medium flex items-center gap-1 mt-1">
                  142 Chunks stored
                </span>
              </div>
              <div className="h-12 w-12 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center">
                <Files className="h-6 w-6" />
              </div>
            </div>
          </div>

          {/* Quick Launch Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                    <Bot className="h-4 w-4" />
                  </div>
                  <h3 className="font-bold text-sm text-slate-800">AI Socratic Tutor</h3>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-medium">
                  Active Provider Ready
                </span>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed mb-4">
                Ask challenging conceptual questions from your study materials. The AI Tutor prompts you with guided reasoning instead of just giving away the final answers.
              </p>
              <button
                onClick={() => setActiveTab('tutor')}
                className="w-full py-2.5 rounded-xl border border-slate-200 hover:border-brand-500 hover:text-brand-600 text-xs font-bold text-slate-700 flex items-center justify-center gap-2 transition-all"
              >
                Launch Tutor Workspace
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                    <HelpCircle className="h-4 w-4" />
                  </div>
                  <h3 className="font-bold text-sm text-slate-800">Adaptive Mock Tests</h3>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 font-medium">
                  Weak Spot Detection
                </span>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed mb-4">
                Generate practice exams from your documents. Questions adapt based on previous quiz attempts to reinforce areas where your confidence score is lowest.
              </p>
              <button
                onClick={() => setActiveTab('quizzes')}
                className="w-full py-2.5 rounded-xl border border-slate-200 hover:border-emerald-500 hover:text-emerald-600 text-xs font-bold text-slate-700 flex items-center justify-center gap-2 transition-all"
              >
                Create Practice Exam
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Upcoming Schedule & System Status */}
          <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-sm text-slate-800 flex items-center gap-2">
                <Calendar className="h-4 w-4 text-brand-600" />
                Upcoming Study Timetable & Review Queue
              </h3>
              <button
                onClick={() => setActiveTab('planner')}
                className="text-xs text-brand-600 font-semibold hover:text-brand-700 flex items-center gap-1"
              >
                Open Full Planner
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-50 border border-slate-100">
                <div className="flex items-center gap-3">
                  <div className="h-2 w-2 rounded-full bg-brand-500" />
                  <div>
                    <p className="text-xs font-bold text-slate-800">CS301: Distributed Consensus & Paxos</p>
                    <p className="text-[11px] text-slate-400">Midterm Exam in 3 Days • High Weight</p>
                  </div>
                </div>
                <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-amber-50 text-amber-700 border border-amber-200">
                  Quiz Scheduled
                </span>
              </div>

              <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-50 border border-slate-100">
                <div className="flex items-center gap-3">
                  <div className="h-2 w-2 rounded-full bg-emerald-500" />
                  <div>
                    <p className="text-xs font-bold text-slate-800">MATH202: Eigenvalues & Singular Value Decomposition</p>
                    <p className="text-[11px] text-slate-400">SM-2 Spaced Review • 12 Cards Due</p>
                  </div>
                </div>
                <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200">
                  Review Due Today
                </span>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
