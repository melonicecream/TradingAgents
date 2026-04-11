'use client'

import { useEffect, useState } from 'react'

interface ExecutionItem {
  id: number
  ticker: string
  analysis_date: string
  status: string
  progress: number
  current_stage?: string | null
  last_completed_milestone?: string | null
  current_milestone?: string | null
  decision?: string | null
  retry_count: number
  resume_count: number
  created_at: string
}

interface ExecutionDetail extends ExecutionItem {
  analysts: string[]
  reports?: Record<string, unknown> | null
  research?: Record<string, unknown> | null
  risk?: Record<string, unknown> | null
  summary_report?: string | null
  started_at: string
  updated_at?: string | null
  elapsed_seconds: number
  workflow_steps: {
    milestone: string
    label: string
    completed_at: string
    elapsed_seconds: number
  }[]
}

interface HistoryPanelProps {
  isAnalyzing: boolean
}

export function HistoryPanel({ isAnalyzing }: HistoryPanelProps) {
  const [executions, setExecutions] = useState<ExecutionItem[]>([])
  const [expandedExecutionId, setExpandedExecutionId] = useState<number | null>(null)
  const [executionDetails, setExecutionDetails] = useState<Record<number, ExecutionDetail>>({})
  const [detailErrors, setDetailErrors] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(false)
  const [detailLoadingId, setDetailLoadingId] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  const API_URL = process.env.NEXT_PUBLIC_API_URL || ''

  const fetchHistory = async () => {
    setLoading(true)

    try {
      const res = await fetch(`${API_URL}/executions?page=${page}&page_size=10`)

      if (!res.ok) {
        throw new Error('Failed to fetch execution history')
      }

      const data = await res.json()
      setExecutions(data.items || [])
      setTotalPages(data.pages || 1)
    } catch (err) {
      console.error('Failed to fetch history:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchExecutionDetail = async (executionId: number) => {
    setDetailLoadingId(executionId)

    try {
      const res = await fetch(`${API_URL}/executions/${executionId}`)

      if (!res.ok) {
        throw new Error('Failed to fetch execution detail')
      }

      const data = (await res.json()) as ExecutionDetail
      setExecutionDetails((prev) => ({
        ...prev,
        [executionId]: data,
      }))
      setDetailErrors((prev) => {
        const next = { ...prev }
        delete next[executionId]
        return next
      })
    } catch (err) {
      console.error('Failed to fetch execution detail:', err)
      setDetailErrors((prev) => ({
        ...prev,
        [executionId]: '상세 실행 정보를 불러오지 못했습니다.',
      }))
    } finally {
      setDetailLoadingId(null)
    }
  }

  useEffect(() => {
    void fetchHistory()
  }, [page])

  useEffect(() => {
    if (!isAnalyzing) {
      void fetchHistory()
    }
  }, [isAnalyzing])

  useEffect(() => {
    if (!isAnalyzing) {
      return
    }

    const intervalId = window.setInterval(() => {
      void fetchHistory()
    }, 3000)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [isAnalyzing, page])

  const handleToggleDetail = async (executionId: number) => {
    if (expandedExecutionId === executionId) {
      setExpandedExecutionId(null)
      return
    }

    setExpandedExecutionId(executionId)

    if (!executionDetails[executionId]) {
      await fetchExecutionDetail(executionId)
    }
  }

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      완료: 'bg-green-100 text-green-700',
      '분석 중': 'bg-blue-100 text-blue-700',
      '재개 가능': 'bg-yellow-100 text-yellow-700',
      실패: 'bg-red-100 text-red-700',
      '대기 중': 'bg-gray-100 text-gray-700',
    }
    return colors[status] || 'bg-gray-100 text-gray-700'
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          분석 이력
        </h3>
        <button
          onClick={() => void fetchHistory()}
          disabled={loading}
          className="text-sm text-blue-600 hover:text-blue-700 disabled:opacity-50"
        >
          {loading ? '로딩...' : '새로고침'}
        </button>
      </div>

      {executions.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          아직 분석 이력이 없습니다.
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {executions.map((item) => {
              const isExpanded = expandedExecutionId === item.id
              const detail = executionDetails[item.id]
              const detailError = detailErrors[item.id]
              const isDetailLoading = detailLoadingId === item.id

              return (
                <div
                  key={item.id}
                  className="p-4 border border-gray-100 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-blue-700 font-bold shrink-0">
                        {item.ticker.slice(0, 2)}
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2 mb-1">
                          <div className="font-medium text-gray-900">{item.ticker}</div>
                          <div className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(item.status)}`}>
                            {item.status}
                          </div>
                        </div>
                        <div className="text-sm text-gray-500">
                          생성 {formatDateTime(item.created_at)} · 분석일 {item.analysis_date}
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => void handleToggleDetail(item.id)}
                      className="self-start px-3 py-2 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-white"
                    >
                      {isExpanded ? '상세 접기' : '상세 보기'}
                    </button>
                  </div>

                  <div className="mt-3">
                    <div className="flex items-center justify-between text-sm text-gray-600 mb-1">
                      <span>{item.current_stage || '대기 중'}</span>
                      <span>{Math.round(item.progress)}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${item.progress}%` }}
                      />
                    </div>
                  </div>

                  <div className="mt-3 flex flex-col gap-2 text-xs text-gray-500 md:flex-row md:items-center md:justify-between">
                    <span>
                      재시도 {item.retry_count}회 · 재개 {item.resume_count}회
                    </span>
                    {item.decision ? (
                      <span>
                        최종 판단: <span className="font-medium text-gray-700">{item.decision}</span>
                      </span>
                    ) : null}
                  </div>

                  {isExpanded && (
                    <div className="mt-4 pt-4 border-t border-gray-200 space-y-4">
                      {isDetailLoading && !detail ? (
                        <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 text-sm text-gray-500">
                          실행 상세 정보를 불러오는 중입니다...
                        </div>
                      ) : null}

                      {detailError ? (
                        <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-sm text-red-700">
                          {detailError}
                        </div>
                      ) : null}

                      {detail ? (
                        <>
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                            <DetailMetric
                              label="실행 시간"
                              value={formatDuration(detail.elapsed_seconds)}
                              hint={`시작 ${formatDateTime(detail.started_at)}`}
                            />
                            <DetailMetric
                              label="업데이트"
                              value={detail.updated_at ? formatDateTime(detail.updated_at) : '업데이트 대기'}
                              hint={detail.current_stage || '단계 정보 없음'}
                            />
                            <DetailMetric
                              label="마지막 마일스톤"
                              value={getMilestoneLabel(detail.last_completed_milestone)}
                              hint={`현재 ${getMilestoneLabel(detail.current_milestone)}`}
                            />
                          </div>

                          {detail.workflow_steps?.length ? (
                            <div className="rounded-lg border border-gray-200 bg-white p-4">
                              <div className="text-sm font-medium text-gray-700 mb-3">실행 단계별 소요 시간</div>
                              <div className="space-y-2">
                                {detail.workflow_steps.map((step) => (
                                  <div key={`${detail.id}-${step.milestone}`} className="flex items-center justify-between gap-4 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-sm">
                                    <div>
                                      <div className="font-medium text-gray-900">{step.label}</div>
                                      <div className="text-xs text-gray-500">{formatDateTime(step.completed_at)} 완료</div>
                                    </div>
                                    <div className="text-sm font-semibold text-gray-700">{formatDuration(step.elapsed_seconds)}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}

                          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                            <div className="text-sm font-medium text-gray-700 mb-3">사용 분석가</div>
                            <div className="flex flex-wrap gap-2">
                              {detail.analysts.map((analyst) => (
                                <span
                                  key={analyst}
                                  className="px-2.5 py-1 rounded-full bg-white border border-gray-200 text-xs font-medium text-gray-700"
                                >
                                  {getAnalystLabel(analyst)}
                                </span>
                              ))}
                            </div>
                          </div>

                          {detail.summary_report ? (
                            <DetailTextBlock
                              title="요약 보고서"
                              content={detail.summary_report}
                              tone="blue"
                            />
                          ) : null}

                          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                            <DetailTextBlock
                              title="투자 계획"
                              content={readObjectText(detail.research, 'investment_plan') || '투자 계획 정보가 없습니다.'}
                            />
                            <DetailTextBlock
                              title="트레이더 계획"
                              content={readObjectText(detail.research, 'trader_plan') || '트레이더 계획 정보가 없습니다.'}
                            />
                            <DetailTextBlock
                              title="리스크 최종 판단"
                              content={readObjectText(detail.risk, 'final_decision') || '리스크 판단 정보가 없습니다.'}
                            />
                            <DetailTextBlock
                              title="보고서 상태"
                              content={buildReportSummary(detail.reports)}
                            />
                          </div>
                        </>
                      ) : null}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <button
                onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                disabled={page === 1}
                className="px-3 py-1 border rounded disabled:opacity-50"
              >
                이전
              </button>
              <span className="text-sm text-gray-600">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                disabled={page === totalPages}
                className="px-3 py-1 border rounded disabled:opacity-50"
              >
                다음
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function DetailMetric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
      <div className="text-xs font-medium text-gray-500 mb-1">{label}</div>
      <div className="text-sm font-semibold text-gray-900">{value}</div>
      <div className="mt-1 text-xs text-gray-500">{hint}</div>
    </div>
  )
}

function DetailTextBlock({
  title,
  content,
  tone = 'default',
}: {
  title: string
  content: string
  tone?: 'default' | 'blue'
}) {
  const toneClassName = tone === 'blue'
    ? 'bg-blue-50 border-blue-100 text-blue-900'
    : 'bg-gray-50 border-gray-200 text-gray-700'

  return (
    <div className={`rounded-lg border p-4 ${toneClassName}`}>
      <div className="text-sm font-medium mb-2">{title}</div>
      <div className="text-sm whitespace-pre-wrap leading-6">{content}</div>
    </div>
  )
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ko-KR')
}

function formatDuration(totalSeconds: number) {
  const roundedSeconds = Math.max(Math.round(totalSeconds), 0)
  const minutes = Math.floor(roundedSeconds / 60)
  const seconds = roundedSeconds % 60

  if (minutes === 0) {
    return `${seconds}초`
  }

  return `${minutes}분 ${seconds}초`
}

function getAnalystLabel(analyst: string) {
  const labels: Record<string, string> = {
    market: '시장 분석가',
    social: '소셜 미디어',
    news: '뉴스 분석가',
    fundamentals: '펀더멘털 분석가',
  }

  return labels[analyst] || analyst
}

function getMilestoneLabel(milestone?: string | null) {
  const labels: Record<string, string> = {
    market_complete: '시장 분석',
    social_complete: '소셜 미디어 분석',
    news_complete: '뉴스 분석',
    fundamentals_complete: '펀더멘털 분석',
    research_complete: '리서치 토론',
    trader_complete: '트레이더 분석',
    risk_complete: '리스크 토론',
    portfolio_complete: '포트폴리오 결정',
  }

  if (!milestone) {
    return '정보 없음'
  }

  return labels[milestone] || milestone
}

function readObjectText(source: Record<string, unknown> | null | undefined, key: string) {
  const value = source?.[key]

  return typeof value === 'string' ? value : ''
}

function buildReportSummary(reports: Record<string, unknown> | null | undefined) {
  if (!reports) {
    return '보고서 메타데이터가 없습니다.'
  }

  const reportLabels: Record<string, string> = {
    market: '시장 분석',
    sentiment: '감성 분석',
    news: '뉴스 분석',
    fundamentals: '펀더멘털 분석',
  }

  const availableReports = Object.entries(reports)
    .filter(([, value]) => typeof value === 'string' && value.trim().length > 0)
    .map(([key]) => reportLabels[key] || key)

  if (availableReports.length === 0) {
    return '저장된 보고서가 없습니다.'
  }

  return `${availableReports.join(', ')} 보고서가 저장되어 있습니다.`
}
