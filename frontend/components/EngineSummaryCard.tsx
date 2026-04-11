'use client'

export interface EngineInfo {
  provider: string
  deep_model: string
  quick_model: string
  backend_url: string
  language: string
  selected_analyst_count: number
  fixed_agent_count: number
  total_agent_count: number
  cli_total_agent_count: number
  agent_count_matches_cli: boolean
  supports_korean_summary: boolean
  engine_explanation?: string | null
}

interface EngineSummaryCardProps {
  engineInfo: EngineInfo | null
  isLoading: boolean
}

export function EngineSummaryCard({ engineInfo, isLoading }: EngineSummaryCardProps) {
  const explanation = engineInfo?.engine_explanation || '선택된 분석가와 고정 실행 에이전트가 함께 동작하는 기본 웹 분석 플로우입니다.'

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">
          엔진 요약
        </h2>
        <span className="text-xs font-medium text-blue-700 bg-blue-50 border border-blue-100 rounded-full px-2.5 py-1">
          {engineInfo?.provider?.toUpperCase() || 'ENGINE'}
        </span>
      </div>

      {isLoading && !engineInfo ? (
        <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 text-sm text-gray-500">
          엔진 정보를 불러오는 중입니다...
        </div>
      ) : engineInfo ? (
        <div className="space-y-4">
          <div className="rounded-lg border border-blue-100 bg-blue-50 p-4">
            <div className="text-xs font-medium text-blue-700 mb-1">엔진 설명</div>
            <p className="text-sm text-blue-900 leading-6">
              {explanation}
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <MetricBlock
              label="Provider"
              value={engineInfo.provider}
              hint={`언어: ${engineInfo.language}`}
            />
            <MetricBlock
              label="총 에이전트 수"
              value={`${engineInfo.total_agent_count}`}
              hint={`분석가 ${engineInfo.selected_analyst_count} · 고정 ${engineInfo.fixed_agent_count} · CLI ${engineInfo.cli_total_agent_count}`}
            />
            <MetricBlock
              label="Deep Model"
              value={engineInfo.deep_model}
              hint="복합 추론 및 요약"
            />
            <MetricBlock
              label="Quick Model"
              value={engineInfo.quick_model}
              hint={engineInfo.supports_korean_summary ? '한국어 요약 지원' : '기본 요약만 지원'}
            />
          </div>

          <div className={`rounded-lg border p-4 ${engineInfo.agent_count_matches_cli ? 'border-green-100 bg-green-50' : 'border-amber-100 bg-amber-50'}`}>
            <div className={`text-sm font-medium ${engineInfo.agent_count_matches_cli ? 'text-green-700' : 'text-amber-700'}`}>
              CLI / Web 에이전트 수
            </div>
            <div className={`mt-1 text-sm ${engineInfo.agent_count_matches_cli ? 'text-green-900' : 'text-amber-900'}`}>
              {engineInfo.agent_count_matches_cli
                ? `Web 기본 구성(${engineInfo.total_agent_count})이 CLI 구성(${engineInfo.cli_total_agent_count})과 일치합니다.`
                : `Web 기본 구성(${engineInfo.total_agent_count})과 CLI 구성(${engineInfo.cli_total_agent_count})이 다릅니다.`}
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 text-sm text-gray-500">
          엔진 정보를 아직 표시할 수 없습니다.
        </div>
      )}
    </div>
  )
}

function MetricBlock({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-1">
        {label}
      </div>
      <div className="text-sm font-semibold text-gray-900 break-all">
        {value}
      </div>
      <div className="mt-1 text-xs text-gray-500">
        {hint}
      </div>
    </div>
  )
}
