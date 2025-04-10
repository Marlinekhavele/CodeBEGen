import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import APP_CONFIG from '~/config'
import Logger from './logger'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const inDevEnvironment =
  !!process && process.env.NODE_ENV === 'development'

export const ROOT_DOMAIN = 'boilerplate.hng.tech'

export const capitalizeFirstLetter = (word: string): string => {
  if (!word) return ''
  return word.charAt(0).toUpperCase() + word.slice(1)
}

export const generateUserInitials = (name: string): string => {
  let userInitials = ''
  userInitials = name
    .split(' ')
    .filter((word) => word.trim() !== '')
    .map((word) => word.charAt(0).toUpperCase())
    .join('')

  return userInitials
}

export async function isProjectUrlHealthy(url: string): Promise<boolean> {
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    if (response.ok) {
      return true
    } else {
      return false
    }
  } catch (error) {
    Logger.error('Error checking health', error)
    return false
  }
}

export const generateId = () => crypto.randomUUID()

const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL

export const getBackendGoogleAuthUrl = (projectId?: string) => {
  const isDev = process.env.NODE_ENV === 'development'

  if (projectId) {
    return isDev
      ? `${baseUrl}/api/v1/auth/login/google?current_project=${projectId}&its_localhost=true`
      : `${baseUrl}/api/v1/auth/login/google?current_project=${projectId}`
  } else {
    return isDev
      ? `${baseUrl}/api/v1/auth/login/google?its_localhost=true`
      : `${baseUrl}/api/v1/auth/login/google`
  }
}

export const formatProjectID = (projectID: string): string => {
  const strArr = projectID.trim().split('-')
  return strArr.slice(0, strArr.length - 1).join(' ')
}

export const getProjectDeployedBaseUrl = (projectId: string) => {
  if (APP_CONFIG.APP_ENV.IS_PROD) {
    return `https://${projectId}.backend.im/im`
  } else {
    return `https://${projectId}.backend.im/dev`
  }
}
