'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Rss,
  Globe,
  Play,
  Settings,
  CheckCircle,
  XCircle,
  AlertCircle,
  RefreshCw
} from 'lucide-react'
import { api, Source } from '@/lib/api'
import { formatDistanceToNow } from 'date-fns'
import { ko } from 'date-fns/locale'

export default function SourcesPage() {
  const [showAddModal, setShowAddModal] = useState(false)
  const queryClient = useQueryClient()

  const { data: sources, isLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: api.getSources,
  })

  const crawlMutation = useMutation({
    mutationFn: (sourceId: string) => api.triggerCrawl(sourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] })
    },
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">소스 관리</h1>
          <p className="text-gray-500 mt-1">크롤링 대상 소스 설정</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          소스 추가
        </button>
      </div>

      {/* Source List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading ? (
          <div className="col-span-full text-center py-12 text-gray-500">로딩 중...</div>
        ) : sources?.length === 0 ? (
          <div className="col-span-full text-center py-12 text-gray-500">
            등록된 소스가 없습니다
          </div>
        ) : (
          sources?.map((source: Source) => (
            <SourceCard
              key={source.id}
              source={source}
              onCrawl={() => crawlMutation.mutate(source.id)}
              isCrawling={crawlMutation.isPending}
            />
          ))
        )}
      </div>

      {/* Add Modal */}
      {showAddModal && (
        <AddSourceModal onClose={() => setShowAddModal(false)} />
      )}
    </div>
  )
}

function SourceCard({
  source,
  onCrawl,
  isCrawling
}: {
  source: Source
  onCrawl: () => void
  isCrawling: boolean
}) {
  const statusIcon = {
    active: <CheckCircle className="w-4 h-4 text-green-500" />,
    inactive: <XCircle className="w-4 h-4 text-gray-400" />,
    error: <AlertCircle className="w-4 h-4 text-red-500" />,
  }

  const typeIcon = source.source_type === 'rss'
    ? <Rss className="w-5 h-5 text-orange-500" />
    : <Globe className="w-5 h-5 text-blue-500" />

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 card-hover">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          {typeIcon}
          <div>
            <h3 className="font-medium text-gray-900">{source.name}</h3>
            <p className="text-sm text-gray-500 truncate max-w-[200px]">{source.url}</p>
          </div>
        </div>
        {statusIcon[source.status as keyof typeof statusIcon]}
      </div>

      <div className="mt-4 space-y-2 text-sm text-gray-500">
        <div className="flex justify-between">
          <span>수집 주기</span>
          <span>{source.crawl_interval_minutes}분</span>
        </div>
        {source.last_crawled_at && (
          <div className="flex justify-between">
            <span>마지막 수집</span>
            <span>
              {formatDistanceToNow(new Date(source.last_crawled_at), {
                addSuffix: true,
                locale: ko
              })}
            </span>
          </div>
        )}
        {source.error_count > 0 && (
          <div className="flex justify-between text-red-500">
            <span>오류 횟수</span>
            <span>{source.error_count}</span>
          </div>
        )}
      </div>

      <div className="mt-4 flex gap-2">
        <button
          onClick={onCrawl}
          disabled={isCrawling}
          className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-primary-50 text-primary-600 rounded-lg hover:bg-primary-100 transition-colors disabled:opacity-50"
        >
          {isCrawling ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          크롤링
        </button>
        <button className="px-3 py-2 text-gray-500 hover:bg-gray-100 rounded-lg transition-colors">
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

function AddSourceModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [type, setType] = useState<'rss' | 'web'>('rss')
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => api.createSource({ name, url, source_type: type }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">새 소스 추가</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">이름</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="TechCrunch AI"
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">URL</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/feed"
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">유형</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as 'rss' | 'web')}
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="rss">RSS 피드</option>
              <option value="web">웹 페이지</option>
            </select>
          </div>
        </div>

        <div className="mt-6 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            취소
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!name || !url || mutation.isPending}
            className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
          >
            {mutation.isPending ? '추가 중...' : '추가'}
          </button>
        </div>
      </div>
    </div>
  )
}
