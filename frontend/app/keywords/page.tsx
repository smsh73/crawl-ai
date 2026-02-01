'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Tag, Trash2, Edit2 } from 'lucide-react'
import { api, KeywordGroup } from '@/lib/api'

export default function KeywordsPage() {
  const [showAddModal, setShowAddModal] = useState(false)
  const queryClient = useQueryClient()

  const { data: groups, isLoading } = useQuery({
    queryKey: ['keywords'],
    queryFn: api.getKeywordGroups,
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">키워드 관리</h1>
          <p className="text-gray-500 mt-1">AI 관련 키워드 그룹 설정</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          그룹 추가
        </button>
      </div>

      {/* Keyword Groups */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="text-center py-12 text-gray-500">로딩 중...</div>
        ) : groups?.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            등록된 키워드 그룹이 없습니다
          </div>
        ) : (
          groups?.map((group: KeywordGroup) => (
            <KeywordGroupCard key={group.id} group={group} />
          ))
        )}
      </div>

      {/* Add Modal */}
      {showAddModal && (
        <AddKeywordGroupModal onClose={() => setShowAddModal(false)} />
      )}
    </div>
  )
}

function KeywordGroupCard({ group }: { group: KeywordGroup }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteKeywordGroup(group.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
    },
  })

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div
        className="p-6 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Tag className="w-5 h-5 text-primary-500" />
            <div>
              <h3 className="font-medium text-gray-900">{group.name}</h3>
              {group.description && (
                <p className="text-sm text-gray-500">{group.description}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">
              {group.keywords?.length || 0}개 키워드
            </span>
            <div className="flex gap-2">
              <button
                className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                <Edit2 className="w-4 h-4" />
              </button>
              <button
                className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                onClick={(e) => {
                  e.stopPropagation()
                  if (confirm('정말 삭제하시겠습니까?')) {
                    deleteMutation.mutate()
                  }
                }}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {isExpanded && group.keywords && group.keywords.length > 0 && (
        <div className="px-6 pb-6 border-t border-gray-100">
          <div className="pt-4 flex flex-wrap gap-2">
            {group.keywords.map((keyword) => (
              <div
                key={keyword.id}
                className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-full"
              >
                <span className="text-sm text-gray-700">{keyword.keyword}</span>
                {keyword.synonyms && keyword.synonyms.length > 0 && (
                  <span className="text-xs text-gray-400">
                    +{keyword.synonyms.length}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function AddKeywordGroupModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [keywordsText, setKeywordsText] = useState('')
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => {
      const keywords = keywordsText
        .split('\n')
        .map(line => line.trim())
        .filter(line => line)
        .map(keyword => ({ keyword, synonyms: null, weight: 1.0 }))

      return api.createKeywordGroup({ name, description, keywords })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">키워드 그룹 추가</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">그룹 이름</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="AI Core"
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">설명 (선택)</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="핵심 AI 관련 키워드"
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              키워드 (줄바꿈으로 구분)
            </label>
            <textarea
              value={keywordsText}
              onChange={(e) => setKeywordsText(e.target.value)}
              placeholder="AI&#10;인공지능&#10;LLM&#10;GPT"
              rows={5}
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
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
            disabled={!name || mutation.isPending}
            className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
          >
            {mutation.isPending ? '추가 중...' : '추가'}
          </button>
        </div>
      </div>
    </div>
  )
}
