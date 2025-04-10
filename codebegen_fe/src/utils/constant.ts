export const URLParameters = {
  CREATE_PROJECT: 'create-backend',
  DATABASE: 'database',
  DASHBOARD: 'dashboard',
  COMING_SOON: 'coming-soon',
  REGISTER: 'register',
  LOGIN: 'login',
  FORGOT_PASSWORD: 'forgot-password',
  PRIVACY: 'privacy',
  PRICING: 'pricing',
  ABOUT: 'about',
  LINKEDIN: 'https://www.linkedin.com/company/backend-im-team/about/',
  YOUTUBE: 'https://www.youtube.com/@BackendIM',
  TIKTOK: 'https://www.tiktok.com/@backend.im',
  WAITLIST: 'https://forms.gle/THGttxet4JBFDeUY8',
  DEPLOYMENT: 'api/v1/ws/deploy',
}

export const autoHeaders = [
  {
    key: 'Cache-Control',
    value: 'no-cache',
    checked: true,
    disabled: true,
  },
  {
    key: 'Content-Length',
    value: 0,
    checked: true,
    disabled: false,
  },
  {
    key: 'Host',
    value: '<calculated when request is sent>',
    checked: true,
    disabled: false,
  },
  {
    key: 'User-Agent',
    value: 'BackendimRuntime/7.43.0',
    checked: true,
    disabled: false,
  },
  {
    key: 'Accept',
    value: '*/*',
    checked: true,
    disabled: false,
  },
]

export const SETTINGS_LINKS = [
  {
    path: '/dashboard/settings/profile',
    navName: 'Profile',
    iconLink: '/images/settings/user-profile.svg',
  },
  {
    path: '/dashboard/settings/pricing',
    navName: 'Pricing',
    iconLink: '/images/settings/cash.svg',
  },
  // {
  //   path: '/dashboard/settings/account',
  //   navName: 'Account',
  //   iconLink: '/images/settings/user-profile.svg',
  // },
]

export const DEPLOYMENT_CONFIG = {
  COMMIT_HASH: 'HEAD',
  START_COMMAND: 'uvicorn main:app --host 0.0.0.0 --port $DEPLOY_PORT',
  PROJECT_TYPE: 'fastapi',
}

export const BACKEND_WS_URL = process.env.NEXT_PUBLIC_API_BASE_URL

export const GOOGLE_FEEDBACK_FORM_URL =
  'https://docs.google.com/forms/d/1JF8RelQeJr1ZHBS2TKRmTDPDaX0AUZbqYsWC15dBPhQ/edit'
