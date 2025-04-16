package v1

import (
	"net/http"
	"{{PROJECT_NAME}}/models"
	"{{PROJECT_NAME}}/services"

	"github.com/gin-gonic/gin"
)

// FormatAuthResponse standardizes the auth response format for v1 API
func FormatAuthResponse(user models.User, token string) gin.H {
	return gin.H{
		"status": "success",
		"data": gin.H{
			"token": token,
			"user": gin.H{
				"id":    user.ID,
				"email": user.Email,
				"name":  user.Name,
			},
		},
	}
}

func FormatErrorResponse(message string) gin.H {
	return gin.H{
		"status":  "error",
		"message": message,
	}
}