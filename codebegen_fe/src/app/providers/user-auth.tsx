import { QueryClient, useMutation, useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import UserAuthService from '~/app/api/services/user-auth-services'
import { getUserQueryOpts } from '~/lib/query-options'

export const useAuth = () => {
  const router = useRouter()
  const queryClient = new QueryClient()
  const { data: user, isError, isPending } = useQuery(getUserQueryOpts)

  const logoutMutation = useMutation({
    mutationFn: () => new UserAuthService().logoutUser(),
    onSuccess: () => {
      queryClient.removeQueries({
        queryKey: ['user'],
        exact: true,
      })
      router.push('/')
    },
  })

  const logoutUser = () => {
    logoutMutation.mutate()
  }

  return {
    user,
    isPending,
    isError,
    logoutUser,
    isLoggingOut: logoutMutation.isPending,
    isLogoutError: logoutMutation.isError,
  }
}
