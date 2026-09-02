"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Newspaper,
  Search,
  Filter,
  ExternalLink,
  Tag,
  Clock,
  Users,
  Database,
  Radio,
  ChevronLeft,
  ChevronRight,
  Loader2,
  X,
  Gauge,
} from "lucide-react";
import Navbar from "../components/Navbar";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Article {
  id: number;
  title: string;
  url: string;
  source_name: string | null;
  published_at: string | null;
  key_takeaway: string | null;
  summary_points: string[] | null;
  tags: string[] | null;
  technical_complexity: number | null;
}

interface Stats {
  total_articles: number;
  articles_today: number;
  active_sources: number;
  active_users: number;
}

const complexityLabels: Record<number, { label: string; color: string }> = {
  1: { label: "Beginner", color: "text-green-400" },
  2: { label: "Easy", color: "text-emerald-400" },
  3: { label: "Intermediate", color: "text-yellow-400" },
  4: { label: "Advanced", color: "text-orange-400" },
  5: { label: "Expert", color: "text-red-400" },
};

export default function DashboardPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [sources, setSources] = useState<{ id: number; name: string }[]>([]);
  const [tags, setTags] = useState<{ tag: string; count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMessage, setLoadingMessage] = useState("Loading AI news archive...");
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 12;

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSource, setSelectedSource] = useState("");
  const [selectedTag, setSelectedTag] = useState("");
  const [selectedDays, setSelectedDays] = useState<number | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  // Hydrate from client cache immediately on mount for 0ms instant display
  useEffect(() => {
    try {
      const cached = sessionStorage.getItem("briefly_dashboard_cache");
      if (cached) {
        const parsed = JSON.parse(cached);
        if (parsed.articles && parsed.articles.length > 0) {
          setArticles(parsed.articles);
          setTotal(parsed.total || parsed.articles.length);
          if (parsed.stats) setStats(parsed.stats);
          if (parsed.sources) setSources(parsed.sources);
          if (parsed.tags) setTags(parsed.tags);
          setLoading(false);
        }
      }
    } catch {
      // Ignore cache parsing errors
    }
  }, []);

  const fetchArticles = useCallback(async () => {
    if (articles.length === 0) {
      setLoading(true);
      setLoadingMessage("Loading AI news archive...");
    }

    const timer = setTimeout(() => {
      setLoadingMessage("Connecting to AI news service — initial wake-up may take a few moments...");
    }, 3500);

    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
      });
      if (searchQuery) params.set("search", searchQuery);
      if (selectedSource) params.set("source", selectedSource);
      if (selectedTag) params.set("tag", selectedTag);
      if (selectedDays) params.set("days", selectedDays.toString());

      const res = await fetch(`${API_URL}/api/articles?${params}`);
      const data = await res.json();
      if (data && data.articles) {
        setArticles(data.articles);
        setTotal(data.total);

        // Cache page 1 baseline data
        if (page === 1 && !searchQuery && !selectedSource && !selectedTag && !selectedDays) {
          try {
            const existingCache = JSON.parse(sessionStorage.getItem("briefly_dashboard_cache") || "{}");
            sessionStorage.setItem(
              "briefly_dashboard_cache",
              JSON.stringify({ ...existingCache, articles: data.articles, total: data.total })
            );
          } catch {}
        }
      }
    } catch (err) {
      console.error("Failed to fetch articles:", err);
    } finally {
      clearTimeout(timer);
      setLoading(false);
    }
  }, [page, searchQuery, selectedSource, selectedTag, selectedDays, articles.length]);

  useEffect(() => {
    fetchArticles();
  }, [fetchArticles]);

  // Fetch stats, sources, and tags on mount
  useEffect(() => {
    const fetchMeta = async () => {
      try {
        const [statsRes, sourcesRes, tagsRes] = await Promise.all([
          fetch(`${API_URL}/api/articles/stats`),
          fetch(`${API_URL}/api/articles/sources`),
          fetch(`${API_URL}/api/articles/tags`),
        ]);
        const statsData = await statsRes.json();
        const sourcesData = await sourcesRes.json();
        const tagsData = await tagsRes.json();

        setStats(statsData);
        setSources(sourcesData);
        setTags(tagsData);

        // Persist to session cache
        try {
          const existingCache = JSON.parse(sessionStorage.getItem("briefly_dashboard_cache") || "{}");
          sessionStorage.setItem(
            "briefly_dashboard_cache",
            JSON.stringify({
              ...existingCache,
              stats: statsData,
              sources: sourcesData,
              tags: tagsData,
            })
          );
        } catch {}
      } catch (err) {
        console.error("Failed to fetch metadata:", err);
      }
    };
    fetchMeta();
  }, []);

  const totalPages = Math.ceil(total / pageSize);

  const clearFilters = () => {
    setSearchQuery("");
    setSelectedSource("");
    setSelectedTag("");
    setSelectedDays(null);
    setPage(1);
  };

  const hasActiveFilters = searchQuery || selectedSource || selectedTag || selectedDays;

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "Unknown";
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <>
      <Navbar />
      <main className="min-h-screen pt-20 pb-12 px-4 sm:px-6 lg:px-8">
        {/* Background Decor */}
        <div className="fixed top-[-10%] left-[-10%] w-[30%] h-[30%] bg-brand-600/10 rounded-full blur-[120px] pointer-events-none" />
        <div className="fixed bottom-[-10%] right-[-10%] w-[30%] h-[30%] bg-purple-600/10 rounded-full blur-[120px] pointer-events-none" />

        <div className="max-w-7xl mx-auto relative z-10">
          {/* Page Header */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8"
          >
            <h1 className="text-3xl sm:text-4xl font-bold tracking-tight mb-2">
              News <span className="text-gradient">Dashboard</span>
            </h1>
            <p className="text-text-muted text-lg">
              Browse and explore curated AI news from across the web.
            </p>
          </motion.div>

          {/* Stats Cards */}
          {stats && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-8"
            >
              {[
                { label: "Total Articles", value: stats.total_articles, icon: Database, color: "text-brand-400" },
                { label: "Today", value: stats.articles_today, icon: Clock, color: "text-emerald-400" },
                { label: "Active Sources", value: stats.active_sources, icon: Radio, color: "text-purple-400" },
                { label: "Subscribers", value: stats.active_users, icon: Users, color: "text-amber-400" },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="glass-card rounded-2xl p-4 sm:p-5"
                >
                  <div className="flex items-center gap-3 mb-2">
                    <stat.icon className={`w-5 h-5 ${stat.color}`} />
                    <span className="text-xs sm:text-sm text-text-muted font-medium">
                      {stat.label}
                    </span>
                  </div>
                  <p className="text-2xl sm:text-3xl font-bold">{stat.value}</p>
                </div>
              ))}
            </motion.div>
          )}

          {/* Search & Filter Bar */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mb-6"
          >
            <div className="flex flex-col sm:flex-row gap-3">
              {/* Search Input */}
              <div className="relative flex-1">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setPage(1);
                  }}
                  placeholder="Search articles..."
                  className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-all placeholder:text-text-muted/50 text-sm"
                />
              </div>

              {/* Filter Toggle */}
              <button
                onClick={() => setShowFilters(!showFilters)}
                className={`flex items-center gap-2 px-5 py-3 rounded-xl border text-sm font-medium transition-all ${
                  showFilters || hasActiveFilters
                    ? "bg-brand-500/20 border-brand-500 text-brand-400"
                    : "bg-white/5 border-white/10 text-text-muted hover:bg-white/10"
                }`}
              >
                <Filter className="w-4 h-4" />
                Filters
                {hasActiveFilters && (
                  <span className="w-2 h-2 rounded-full bg-brand-400" />
                )}
              </button>

              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className="flex items-center gap-2 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-text-muted hover:text-white text-sm transition-all"
                >
                  <X className="w-4 h-4" />
                  Clear
                </button>
              )}
            </div>

            {/* Expanded Filters */}
            {showFilters && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="mt-4 glass-card rounded-2xl p-5 grid grid-cols-1 sm:grid-cols-3 gap-4"
              >
                {/* Source Filter */}
                <div>
                  <label className="block text-xs font-medium text-text-muted mb-2 uppercase tracking-wider">
                    Source
                  </label>
                  <select
                    value={selectedSource}
                    onChange={(e) => {
                      setSelectedSource(e.target.value);
                      setPage(1);
                    }}
                    className="w-full px-3 py-2.5 bg-white/5 border border-white/10 rounded-lg text-sm outline-none focus:border-brand-500 transition-all"
                  >
                    <option value="">All Sources</option>
                    {sources.map((s) => (
                      <option key={s.id} value={s.name}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Tag Filter */}
                <div>
                  <label className="block text-xs font-medium text-text-muted mb-2 uppercase tracking-wider">
                    Tag
                  </label>
                  <select
                    value={selectedTag}
                    onChange={(e) => {
                      setSelectedTag(e.target.value);
                      setPage(1);
                    }}
                    className="w-full px-3 py-2.5 bg-white/5 border border-white/10 rounded-lg text-sm outline-none focus:border-brand-500 transition-all"
                  >
                    <option value="">All Tags</option>
                    {tags.slice(0, 25).map((t) => (
                      <option key={t.tag} value={t.tag}>
                        {t.tag} ({t.count})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Time Range Filter */}
                <div>
                  <label className="block text-xs font-medium text-text-muted mb-2 uppercase tracking-wider">
                    Time Range
                  </label>
                  <select
                    value={selectedDays ?? ""}
                    onChange={(e) => {
                      setSelectedDays(e.target.value ? parseInt(e.target.value) : null);
                      setPage(1);
                    }}
                    className="w-full px-3 py-2.5 bg-white/5 border border-white/10 rounded-lg text-sm outline-none focus:border-brand-500 transition-all"
                  >
                    <option value="">All Time</option>
                    <option value="1">Today</option>
                    <option value="7">Last 7 days</option>
                    <option value="30">Last 30 days</option>
                    <option value="90">Last 90 days</option>
                  </select>
                </div>
              </motion.div>
            )}
          </motion.div>

          {/* Results Count */}
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-text-muted">
              {total} article{total !== 1 ? "s" : ""} found
            </p>
          </div>

          {/* Article Grid */}
          {loading ? (
            <div className="flex flex-col items-center justify-center py-24 gap-3">
              <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
              <p className="text-sm font-medium text-brand-200 animate-pulse">
                {loadingMessage}
              </p>
            </div>
          ) : articles.length === 0 ? (
            <div className="text-center py-20 glass-card rounded-2xl p-8 max-w-md mx-auto">
              <Newspaper className="w-12 h-12 text-text-muted mx-auto mb-4" />
              <p className="text-text-muted text-lg font-medium">No articles found.</p>
              {searchQuery || selectedSource || selectedTag || selectedDays ? (
                <>
                  <p className="text-text-muted/60 text-sm mt-1 mb-4">
                    No articles match your active filter criteria.
                  </p>
                  <button
                    onClick={clearFilters}
                    className="px-4 py-2 bg-brand-500/20 hover:bg-brand-500/30 text-brand-300 text-sm rounded-lg transition-colors"
                  >
                    Reset Filters
                  </button>
                </>
              ) : (
                <>
                  <p className="text-text-muted/60 text-sm mt-1 mb-4">
                    The backend archive is currently waking up or empty. Daily curation runs at 7:00 AM UTC.
                  </p>
                  <button
                    onClick={fetchArticles}
                    className="px-4 py-2 bg-brand-500/20 hover:bg-brand-500/30 text-brand-300 text-sm rounded-lg transition-colors"
                  >
                    Refresh Dashboard
                  </button>
                </>
              )}
            </div>
          ) : (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.1 }}
              className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-5"
            >
              {articles.map((article, i) => (
                <motion.article
                  key={article.id}
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="glass-card rounded-2xl p-5 sm:p-6 flex flex-col hover:border-white/10 transition-all group"
                >
                  {/* Source & Date */}
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-medium text-brand-400 bg-brand-500/10 px-2.5 py-1 rounded-full">
                      {article.source_name || "Unknown"}
                    </span>
                    <span className="text-xs text-text-muted">
                      {formatDate(article.published_at)}
                    </span>
                  </div>

                  {/* Title */}
                  <h3 className="text-base sm:text-lg font-semibold leading-snug mb-3 line-clamp-2 group-hover:text-brand-100 transition-colors">
                    {article.title}
                  </h3>

                  {/* Key Takeaway */}
                  {article.key_takeaway && (
                    <p className="text-sm text-text-muted leading-relaxed mb-4 line-clamp-3">
                      {article.key_takeaway}
                    </p>
                  )}

                  {/* Tags */}
                  {article.tags && article.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-4">
                      {article.tags.slice(0, 4).map((tag) => (
                        <span
                          key={tag}
                          className="text-xs px-2 py-0.5 rounded-full bg-white/5 text-text-muted border border-white/5"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Footer */}
                  <div className="mt-auto flex items-center justify-between pt-3 border-t border-white/5">
                    {/* Complexity */}
                    {article.technical_complexity && article.technical_complexity > 0 && (
                      <div className="flex items-center gap-1.5">
                        <Gauge className="w-3.5 h-3.5 text-text-muted" />
                        <span
                          className={`text-xs font-medium ${
                            complexityLabels[article.technical_complexity]?.color || "text-text-muted"
                          }`}
                        >
                          {complexityLabels[article.technical_complexity]?.label || "Unknown"}
                        </span>
                      </div>
                    )}

                    {/* Read More */}
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-xs font-medium text-brand-400 hover:text-brand-100 transition-colors ml-auto"
                    >
                      Read article
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </motion.article>
              ))}
            </motion.div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 mt-8">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="p-2 rounded-lg bg-white/5 border border-white/10 text-text-muted hover:bg-white/10 disabled:opacity-30 transition-all"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              <span className="text-sm text-text-muted">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page === totalPages}
                className="p-2 rounded-lg bg-white/5 border border-white/10 text-text-muted hover:bg-white/10 disabled:opacity-30 transition-all"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
