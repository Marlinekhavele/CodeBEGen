'use client'

import { usePathname, useSearchParams } from 'next/navigation'
import posthog from 'posthog-js'
import { PostHogProvider as PHProvider, usePostHog } from 'posthog-js/react'
import { Suspense, useEffect } from 'react'
import APP_CONFIG from '~/config'

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    if (APP_CONFIG.APP_ENV.IS_PROD) {
      posthog.init(APP_CONFIG.POSTHOG.API_KEY, {
        api_host: '/ingest',
        ui_host: 'https://us.posthog.com',
        capture_pageview: false, // We capture pageviews manually
        capture_pageleave: true, // Enable pageleave capture
      })
    }
  }, [])

  return (
    <PHProvider client={posthog}>
      <SuspendedPostHogPageView />
      {children}
    </PHProvider>
  )
}

function PostHogPageView() {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const posthogClient = usePostHog()

  useEffect(() => {
    if (pathname && posthogClient) {
      let url = window.origin + pathname
      const search = searchParams.toString()
      if (search) {
        url += '?' + search
      }
      if (APP_CONFIG.APP_ENV.IS_PROD) {
        posthogClient.capture('$pageview', { $current_url: url })
      }
    }
  }, [pathname, searchParams, posthogClient])

  return null
}

function SuspendedPostHogPageView() {
  return (
    <Suspense fallback={null}>
      <PostHogPageView />
    </Suspense>
  )
}
