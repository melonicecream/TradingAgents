'use client'

import { useState } from 'react'
import type { EngineInfo } from '@/components/EngineSummaryCard'

interface ResultPanelProps {
  result: {
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
  engineInfo?: EngineInfo | null
  executionDetail?: {
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
    summary_report?: string | null
    started_at: string
    updated_at?: string | null
    elapsed_seconds: number
    workflow_steps?: {
      milestone: string
      label: string
      completed_at: string
      elapsed_seconds: number
    }[]
  } | null
}

const DECISION_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  Buy: { label: '매수', color: 'text-green-700', bg: 'bg-green-100' },
  Overweight: { label: '비중 확대', color: 'text-green-600', bg: 'bg-green-50' },
  Hold: { label: '보유', color: 'text-yellow-700', bg: 'bg-yellow-100' },
  Underweight: { label: '비중 축소', color: 'text-orange-700', bg: 'bg-orange-100' },
  Sell: { label: '매도', color: 'text-red-700', bg: 'bg-red-100' },
}

export function ResultPanel({ result, engineInfo, executionDetail }: ResultPanelProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'reports' | 'debates'>('overview')

  const decision = DECISION_CONFIG[result.decision] || { label: result.decision, color: 'text-gray-700', bg: 'bg-gray-100' }
  const summaryReport = result.translated_summary || result.summary_report || executionDetail?.summary_report || ''
  const engineExplanation = result.engine_explanation || engineInfo?.engine_explanation || ''

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="p-6 border-b border-gray-200">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">
            분석 결과
          </h3>
          <div className={`px-4 py-2 rounded-full ${decision.bg}`}>
            <span className={`text-lg font-bold ${decision.color}`}>
              최종 결정: {decision.label}
            </span>
          </div>
        </div>

        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
          {[
            { id: 'overview', label: '개요' },
            { id: 'reports', label: '분석 보고서' },
            { id: 'debates', label: '토론 내용' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as 'overview' | 'reports' | 'debates')}
              className={`flex-1 py-2 px-4 text-sm font-medium rounded-md transition-colors ${
                activeTab === tab.id
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="p-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {(summaryReport || engineExplanation) && (
              <div className="grid grid-cols-1 gap-4">
                {summaryReport && (
                  <div className="bg-blue-50 border border-blue-100 rounded-lg p-4">
                    <div className="text-sm font-medium text-blue-700 mb-2">번역/요약 보고서</div>
                    <div className="text-sm text-blue-900 whitespace-pre-wrap leading-6">
                      {summaryReport}
                    </div>
                  </div>
                )}

                {engineExplanation && (
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                    <div className="text-sm font-medium text-slate-700 mb-2">엔진 설명</div>
                    <div className="text-sm text-slate-800 leading-6 whitespace-pre-wrap">
                      {engineExplanation}
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <MetaCard
                label="실행 메타데이터"
                value={`#${executionDetail?.id || result.execution_id || '-'}`}
                hint={`${executionDetail?.status || result.status || '상태 정보 없음'}${executionDetail?.current_stage ? ` · ${executionDetail.current_stage}` : ''}`}
              />
              <MetaCard
                label="실행 시간"
                value={executionDetail ? formatDuration(executionDetail.elapsed_seconds) : '집계 중'}
                hint={executionDetail?.started_at ? `시작 ${formatDateTime(executionDetail.started_at)}` : '완료 후 상세 정보 제공'}
              />
              <MetaCard
                label="Provider / 언어"
                value={engineInfo ? `${engineInfo.provider} · ${engineInfo.language}` : '엔진 정보 없음'}
                hint={engineInfo?.supports_korean_summary ? '한국어 요약 지원' : '기본 응답만 표시'}
              />
              <MetaCard
                label="모델 / 에이전트"
                value={engineInfo ? `${engineInfo.deep_model} / ${engineInfo.quick_model}` : '엔진 정보 없음'}
                hint={engineInfo ? `총 ${engineInfo.total_agent_count}개 에이전트 · CLI ${engineInfo.cli_total_agent_count}` : '기본 웹 플로우'}
              />
            </div>

            {executionDetail?.workflow_steps?.length ? (
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div className="text-sm font-medium text-gray-700 mb-3">단계별 소요 시간</div>
                <div className="space-y-2">
                  {executionDetail.workflow_steps.map((step) => (
                    <div key={`${executionDetail.id}-${step.milestone}`} className="flex items-center justify-between gap-4 rounded-lg border border-gray-100 bg-white px-3 py-2 text-sm">
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

            {executionDetail?.analysts?.length ? (
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div className="text-sm font-medium text-gray-700 mb-3">사용 분석가</div>
                <div className="flex flex-wrap gap-2">
                  {executionDetail.analysts.map((analyst) => (
                    <span
                      key={analyst}
                      className="px-2.5 py-1 rounded-full bg-white border border-gray-200 text-xs font-medium text-gray-700"
                    >
                      {getAnalystLabel(analyst)}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <ReportCard
                title="시장 분석"
                content={result.reports.market}
                icon="📊"
              />
              <ReportCard
                title="감성 분석"
                content={result.reports.sentiment}
                icon="💭"
              />
              <ReportCard
                title="뉴스 분석"
                content={result.reports.news}
                icon="📰"
              />
              <ReportCard
                title="펀더멘털 분석"
                content={result.reports.fundamentals}
                icon="📈"
              />
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <TextPanel
                title="투자 계획"
                content={result.research.investment_plan || '투자 계획이 생성되지 않았습니다.'}
              />
              <TextPanel
                title="트레이더 계획"
                content={result.research.trader_plan || '트레이더 계획이 생성되지 않았습니다.'}
              />
            </div>
          </div>
        )}

        {activeTab === 'reports' && (
          <div className="space-y-6">
            <ReportSection title="시장 분석 보고서" content={result.reports.market} />
            <ReportSection title="감성 분석 보고서" content={result.reports.sentiment} />
            <ReportSection title="뉴스 분석 보고서" content={result.reports.news} />
            <ReportSection title="펀더멘털 분석 보고서" content={result.reports.fundamentals} />
          </div>
        )}

        {activeTab === 'debates' && (
          <div className="space-y-6">
            <DebateSection
              title="투자 찬반 토론"
              bull={result.research.bull_history}
              bear={result.research.bear_history}
            />
            <DebateSection
              title="리스크 평가 토론"
              aggressive={result.risk.aggressive}
              conservative={result.risk.conservative}
              neutral={result.risk.neutral}
              final={result.risk.final_decision}
            />
          </div>
        )}
      </div>
    </div>
  )
}

function MetaCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
      <div className="text-xs font-medium text-gray-500 mb-1">{label}</div>
      <div className="text-sm font-semibold text-gray-900 break-all">{value}</div>
      <div className="mt-1 text-xs text-gray-500">{hint}</div>
    </div>
  )
}

function TextPanel({ title, content }: { title: string; content: string }) {
  return (
    <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
      <h4 className="font-medium text-gray-900 mb-2">{title}</h4>
      <div className="text-sm text-gray-700 whitespace-pre-wrap leading-6">
        {content}
      </div>
    </div>
  )
}

function ReportCard({ title, content, icon }: { title: string; content: string; icon: string }) {
  const hasContent = content && content.length > 10

  return (
    <div className={`p-4 rounded-lg border ${hasContent ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-2xl">{icon}</span>
        <span className="font-medium text-gray-900">{title}</span>
      </div>
      <div className={`text-xs ${hasContent ? 'text-green-700' : 'text-gray-500'}`}>
        {hasContent ? '✓ 분석 완료' : '분석 데이터 없음'}
      </div>
    </div>
  )
}

function ReportSection({ title, content }: { title: string; content: string }) {
  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <h4 className="font-medium text-gray-900 mb-3">{title}</h4>
      <div className="text-sm text-gray-700 whitespace-pre-wrap max-h-96 overflow-y-auto leading-6">
        {content || '보고서 내용이 없습니다.'}
      </div>
    </div>
  )
}

function DebateSection({
  title,
  bull,
  bear,
  aggressive,
  conservative,
  neutral,
  final,
}: {
  title: string
  bull?: string
  bear?: string
  aggressive?: string
  conservative?: string
  neutral?: string
  final?: string
}) {
  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <h4 className="font-medium text-gray-900 mb-4">{title}</h4>

      {bull && bear && (
        <div className="space-y-4">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="font-medium text-green-800 mb-2">🐂 공시적(Optimistic) 관점</div>
            <div className="text-sm text-green-700 whitespace-pre-wrap leading-6">{bull}</div>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="font-medium text-red-800 mb-2">🐻 비관적(Pessimistic) 관점</div>
            <div className="text-sm text-red-700 whitespace-pre-wrap leading-6">{bear}</div>
          </div>
        </div>
      )}

      {aggressive && conservative && neutral && (
        <div className="space-y-4">
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
            <div className="font-medium text-orange-800 mb-2">⚡ 공격적 리스크 분석</div>
            <div className="text-sm text-orange-700 whitespace-pre-wrap leading-6">{aggressive}</div>
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="font-medium text-blue-800 mb-2">🛡️ 보수적 리스크 분석</div>
            <div className="text-sm text-blue-700 whitespace-pre-wrap leading-6">{conservative}</div>
          </div>
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <div className="font-medium text-gray-800 mb-2">⚖️ 중립적 리스크 분석</div>
            <div className="text-sm text-gray-700 whitespace-pre-wrap leading-6">{neutral}</div>
          </div>
          {final && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <div className="font-medium text-purple-800 mb-2">📋 최종 리스크 판단</div>
              <div className="text-sm text-purple-700 whitespace-pre-wrap leading-6">{final}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
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

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ko-KR')
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
