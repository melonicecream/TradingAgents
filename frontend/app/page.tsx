'use client'

import { useCallback, useEffect, useState } from 'react'
import { AnalysisForm } from '@/components/AnalysisForm'
import { EngineSummaryCard, type EngineInfo } from '@/components/EngineSummaryCard'
import { ProgressPanel } from '@/components/ProgressPanel'
import { ResultPanel } from '@/components/ResultPanel'
import { HistoryPanel } from '@/components/HistoryPanel'
import { Header } from '@/components/Header'
import { SystemStatsPanel, type SystemStats } from '@/components/SystemStatsPanel'

interface AnalysisResult {
  type: 'complete'
  decision: string
  execution_id?: number
  status?: string
  thread_id?: string
  summary_report?: string | null
  translated_summary?: string | null
  engine_explanation?: string | null
  reports: {
    market: string
    sentiment: string
    news: string
    fundamentals: string
  }
  research: {
    investment_plan: string
    trader_plan: string
    bull_history: string
    bear_history: string
  }
  risk: {
    aggressive: string
    conservative: string
    neutral: string
    final_decision: string
  }
}

interface ProgressData {
  type: 'progress'
  step: number
  total: number
  progress: number
  elapsed_seconds?: number
  agent: string | null
  current_stage: string | null
  agent_status: Record<string, string>
  milestone_status: Record<string, string>
  completed_milestones: number
  total_milestones: number
  reports: Record<string, string>
}

interface ExecutionDetail {
  id: number
  ticker: string
  analysis_date: string
  status: string
  progress: number
  current_stage?: string | null
  last_completed_milestone?: string | null
  current_milestone?: string | null
  retry_count: number
  resume_count: number
  decision?: string | null
  created_at: string
  analysts: string[]
  reports?: Record<string, unknown> | null
  research?: Record<string, unknown> | null
  risk?: Record<string, unknown> | null
  summary_report?: string | null
  started_at: string
  updated_at?: string | null
  elapsed_seconds: number
}

export default function Home() {
  const API_URL = process.env.NEXT_PUBLIC_API_URL || ''
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [engineInfo, setEngineInfo] = useState<EngineInfo | null>(null)
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null)
  const [latestExecutionDetail, setLatestExecutionDetail] = useState<ExecutionDetail | null>(null)
  const [isEngineLoading, setIsEngineLoading] = useState(true)
  const [isStatsLoading, setIsStatsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchEngineInfo = useCallback(async () => {
    setIsEngineLoading(true)

    try {
      const res = await fetch(`${API_URL}/engine`)

      if (!res.ok) {
        throw new Error('Failed to fetch engine info')
      }

      const data = (await res.json()) as EngineInfo
      setEngineInfo(data)
    } catch (err) {
      console.error('Failed to fetch engine info:', err)
    } finally {
      setIsEngineLoading(false)
    }
  }, [API_URL])

  const fetchSystemStats = useCallback(async () => {
    setIsStatsLoading(true)

    try {
      const res = await fetch(`${API_URL}/stats`)

      if (!res.ok) {
        throw new Error('Failed to fetch system stats')
      }

      const data = (await res.json()) as SystemStats
      setSystemStats(data)
    } catch (err) {
      console.error('Failed to fetch system stats:', err)
    } finally {
      setIsStatsLoading(false)
    }
  }, [API_URL])

  const fetchExecutionDetail = useCallback(
    async (executionId: number) => {
      try {
        const res = await fetch(`${API_URL}/executions/${executionId}`)

        if (!res.ok) {
          throw new Error('Failed to fetch execution detail')
        }

        const data = (await res.json()) as ExecutionDetail
        setLatestExecutionDetail(data)
      } catch (err) {
        console.error('Failed to fetch execution detail:', err)
      }
    },
    [API_URL]
  )

  useEffect(() => {
    void fetchEngineInfo()
    void fetchSystemStats()
  }, [fetchEngineInfo, fetchSystemStats])

  useEffect(() => {
    if (!isAnalyzing) {
      return
    }

    const intervalId = window.setInterval(() => {
      void fetchSystemStats()
    }, 3000)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [fetchSystemStats, isAnalyzing])

  const startAnalysis = async (ticker: string, date: string, analysts: string[]) => {
    setIsAnalyzing(true)
    setProgress(null)
    setResult(null)
    setLatestExecutionDetail(null)
    setError(null)
    void fetchSystemStats()

    try {
      const eventSource = new EventSource(
        `${API_URL}/analyze/${encodeURIComponent(ticker)}?date=${date}&analysts=${analysts.join(',')}`
      )

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data) as AnalysisResult | { type: 'progress' } | { type: 'error'; message?: string }

        if (data.type === 'progress') {
          setProgress(data as ProgressData)
        } else if (data.type === 'complete') {
          setResult(data)
          setIsAnalyzing(false)
          eventSource.close()
          void fetchSystemStats()

          if (typeof data.execution_id === 'number') {
            void fetchExecutionDetail(data.execution_id)
          }
        } else if (data.type === 'error') {
          setError(data.message || '분석 중 오류가 발생했습니다.')
          setIsAnalyzing(false)
          eventSource.close()
          void fetchSystemStats()
        }
      }

      eventSource.onerror = () => {
        setError('서버 연결 오류가 발생했습니다.')
        setIsAnalyzing(false)
        eventSource.close()
        void fetchSystemStats()
      }
    } catch (err) {
      setError('분석 시작 중 오류가 발생했습니다.')
      setIsAnalyzing(false)
      void fetchSystemStats()
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <Header />

      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            AI 주식 분석 에이전트
          </h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            12개의 전문 AI 에이전트가 협업하여 종목을 심층 분석합니다.
            시장 분석, 뉴스, 소셜 미디어, 펀더멘털을 종합 판단합니다.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-6">
            <AnalysisForm
              onSubmit={startAnalysis}
              isLoading={isAnalyzing}
            />

            <EngineSummaryCard
              engineInfo={engineInfo}
              isLoading={isEngineLoading}
            />
          </div>

          <div className="lg:col-span-2 space-y-6">
            <SystemStatsPanel
              stats={systemStats}
              isLoading={isStatsLoading}
            />

            {isAnalyzing && progress && (
              <ProgressPanel progress={progress} />
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
                {error}
              </div>
            )}

            {result && (
              <ResultPanel
                result={result}
                engineInfo={engineInfo}
                executionDetail={latestExecutionDetail}
              />
            )}

            {!isAnalyzing && !result && !error && (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
                <div className="text-gray-400 mb-4">
                  <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  분석을 시작하세요
                </h3>
                <p className="text-gray-500">
                  왼쪽에서 종목 코드와 날짜를 입력하고 분석을 시작하세요.
                </p>
              </div>
            )}

            <HistoryPanel isAnalyzing={isAnalyzing} />
          </div>
        </div>
      </div>
    </main>
  )
}
