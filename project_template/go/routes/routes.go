package routes

import (
	"{{PROJECT_NAME}}/controllers"
	"{{PROJECT_NAME}}/middleware"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

func SetupRoutes(r *gin.Engine, db *gorm.DB) {

	authController := controllers.NewAuthController(db)

	v1 := r.Group("/api/v1")
	{
		auth := v1.Group("/auth")
		{
			auth.POST("/login", authController.Login)
			auth.POST("/signup", authController.Signup)
		}

		protected := v1.Group("/")
		protected.Use(middleware.AuthMiddleware())
		{
			protected.GET("/user", func(c *gin.Context) {
				userID, _ := c.Get("user_id")
				c.JSON(200, gin.H{"user_id": userID})
			})
		}
	}
}