export const getValidSubdomain = (host?: string | null) => {
  let subdomain: string = ''
  if (host && host.endsWith('.backend.im')) {
    const candidate = host.split('.')[0]
    if (candidate && candidate !== 'dev') {
      subdomain = candidate
    }
  }
  return subdomain
}
