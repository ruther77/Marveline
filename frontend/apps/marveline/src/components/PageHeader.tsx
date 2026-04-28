/**
 * PageHeader auto-connecté au HeaderTitleContext.
 * Proxy vers le PageHeader shared + câblage automatique du crossfade.
 * Les pages n'ont plus qu'à faire : <PageHeader title="..." />
 */
import { useCallback } from 'react'
import { PageHeader as BasePageHeader } from '@shared/components/ui'
import type { PageHeaderProps as BaseProps } from '@shared/components/ui'
import { useHeaderTitle } from '@/layout/HeaderTitleContext'

export type PageHeaderProps = Omit<BaseProps, 'onTitleChange' | 'onProgressChange'>

export function PageHeader(props: PageHeaderProps) {
  const { setTitle, setProgress } = useHeaderTitle()
  const onTitleChange = useCallback((t: string) => setTitle(t), [setTitle])
  const onProgressChange = useCallback((p: number) => setProgress(p), [setProgress])

  return (
    <BasePageHeader
      {...props}
      onTitleChange={onTitleChange}
      onProgressChange={onProgressChange}
    />
  )
}
