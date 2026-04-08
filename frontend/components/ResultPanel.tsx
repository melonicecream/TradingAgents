'use client'

import { useState } from 'react'

interface ResultPanelProps {
  result: {
    decision: string
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
}

const DECISION_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  'Buy': { label: '매수', color: 'text-green-700', bg: 'bg-green-100' },
  'Overweight': { label: '비중 확대', color: 'text-green-600', bg: 'bg-green-50' },
  'Hold': { label: '보유', color: 'text-yellow-700', bg: 'bg-yellow-100' },
  'Underweight': { label: '비중 축소', color: 'text-orange-700', bg: 'bg-orange-100' },
  'Sell': { label: '매도', color: 'text-red-700', bg: 'bg-red-100' },
}

export function ResultPanel({ result }: ResultPanelProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'reports' | 'debates'>('overview')
  
  const decision = DECISION_CONFIG[result.decision] || { label: result.decision, color: 'text-gray-700', bg: 'bg-gray-100' }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      {/* Header with Decision */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">
            분석 결과
          </h3>
          <div className={`px-4 py-2 rounded-full ${decision.bg}`}>
            <span className={`text-lg font-bold ${decision.color}`}>
              최종 결정: {decision.label}
            </span>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
          {[
            { id: 'overview', label: '개요' },
            { id: 'reports', label: '분석 보고서' },
            { id: 'debates', label: '토론 내용' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
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

      {/* Content */}
      <div className="p-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
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

            <div className="bg-gray-50 rounded-lg p-4">
              <h4 className="font-medium text-gray-900 mb-2">투자 계획</h4>
              <div className="text-sm text-gray-700 whitespace-pre-wrap">
                {result.research.investment_plan || '투자 계획이 생성되지 않았습니다.'}
              </div>
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
      <div className="text-sm text-gray-700 whitespace-pre-wrap max-h-96 overflow-y-auto">
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
  final 
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
            <div className="text-sm text-green-700 whitespace-pre-wrap">{bull}</div>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="font-medium text-red-800 mb-2">🐻 비관적(Pessimistic) 관점</div>
            <div className="text-sm text-red-700 whitespace-pre-wrap">{bear}</div>
          </div>
        </div>
      )}

      {aggressive && conservative && neutral && (
        <div className="space-y-4">
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
            <div className="font-medium text-orange-800 mb-2">⚡ 공격적 리스크 분석</div>
            <div className="text-sm text-orange-700 whitespace-pre-wrap">{aggressive}</div>
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="font-medium text-blue-800 mb-2">🛡️ 보수적 리스크 분석</div>
            <div className="text-sm text-blue-700 whitespace-pre-wrap">{conservative}</div>
          </div>
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <div className="font-medium text-gray-800 mb-2">⚖️ 중립적 리스크 분석</div>
            <div className="text-sm text-gray-700 whitespace-pre-wrap">{neutral}</div>
          </div>
          {final && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <div className="font-medium text-purple-800 mb-2">📋 최종 리스크 판단</div>
              <div className="text-sm text-purple-700 whitespace-pre-wrap">{final}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
