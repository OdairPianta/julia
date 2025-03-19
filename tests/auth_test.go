package tests

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/OdairPianta/julia/config"
	"github.com/OdairPianta/julia/models"
	"github.com/OdairPianta/julia/tests/fakers"
	"golang.org/x/crypto/bcrypt"

	"github.com/stretchr/testify/assert"
)

func TestUserLogin(t *testing.T) {
	setupDatabase()
	router := routesSetup()
	user, _ := initUser()
	user.Email = fakers.Email()

	hashedPassword, err := bcrypt.GenerateFromPassword([]byte("123456"), bcrypt.DefaultCost)
	assert.Nil(t, err)
	user.Password = string(hashedPassword)
	err = config.DB.Save(&user).Error
	assert.Nil(t, err)

	body := []byte(`{"email": "` + user.Email + `", "password": "123456"}`)

	req, _ := http.NewRequest("POST", "/api/login", bytes.NewBuffer(body))
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, req)

	assert.Equal(t, http.StatusOK, recorder.Code, "OK response is expected")

	var result map[string]string
	_ = json.Unmarshal(recorder.Body.Bytes(), &result)
	assert.NotNil(t, result, "response body must be a valid json")
	assert.NotEmpty(t, result["token"], "token must be not empty")

	var resultModel models.User
	err = json.Unmarshal(recorder.Body.Bytes(), &resultModel)
	assert.Nil(t, err, "Returned body: "+recorder.Body.String())
}

func TestUserRecoverPassword(t *testing.T) {
	setupDatabase()
	router := routesSetup()
	user, _ := initUser()

	body := []byte(`{"reset_password_token": "` + user.ResetPasswordToken + `", "password": "123456"}`)

	req, _ := http.NewRequest("POST", "/api/recover_password", bytes.NewBuffer(body))
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, req)

	assert.Equal(t, http.StatusOK, recorder.Code, "OK response is expected")
}
