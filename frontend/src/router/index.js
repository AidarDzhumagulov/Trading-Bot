import { createRouter, createWebHistory } from 'vue-router'
import LoginPage from "../components/LoginPage.vue"
import RegisterPage from "../components/RegisterPage.vue"
import DashboardPage from "../components/DashboardPage.vue"
import {isAuthenticated} from "../stores/authStore.js"


const routes = [
    {
        path: '/',
        redirect: '/dashboard'
    },
    {
        path: '/login',
        name: 'Login',
        component: LoginPage,
        meta: {requiresAuth: false}
    },
    {
        path: '/register',
        name: 'Register',
        component: RegisterPage,
        meta: {requiresAuth: false}
    },
    {
        path: '/dashboard',
        name: 'Dashboard',
        component: DashboardPage,
        meta: {requiresAuth: true}
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

router.beforeEach((to, from, next) => {
    const authRequired = to.meta.requiresAuth
    const loggedIn = isAuthenticated()

    if (authRequired && !loggedIn) {
        next('/login')
    } else if (!authRequired && loggedIn && (to.path === '/login' || to.path === '/register')) {
        next('/dashboard')
    } else {
        next()
    }
})

export default router