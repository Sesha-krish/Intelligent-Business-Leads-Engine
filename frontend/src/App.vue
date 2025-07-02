<template>
<div class="text-end mb-2">
  <button @click="toggleTheme" class="btn btn-sm btn-outline-secondary">
    {{ isDarkMode ? '☀️ Light Mode' : '🌙 Dark Mode' }}
  </button>
</div>

  <div class="container mt-4">
    <!-- Initial Choice Screen -->
    <transition name="fade">
      <div v-if="!userType" class="choice-screen text-center">
        <h1 class="display-4 mb-3">Dual-Persona Lead Engine</h1>
        <p class="lead text-muted mb-5">Are you looking for talent or for a new opportunity?</p>
        <div class="row">
          <div class="col-md-6 mb-3">
            <div class="card h-100 card-choice" @click="setUserType('recruiter')">
              <div class="card-body">
                <h2 class="card-title">👨‍💼</h2>
                <h3 class="card-subtitle mb-2">For Recruiters</h3>
                <p class="card-text">Find and rank top talent based on their digital footprint and activity.</p>
              </div>
            </div>
          </div>
          <div class="col-md-6 mb-3">
            <div class="card h-100 card-choice" @click="setUserType('seeker')">
              <div class="card-body">
                <h2 class="card-title">🚀</h2>
                <h3 class="card-subtitle mb-2">For Job Seekers</h3>
                <p class="card-text">Discover and evaluate companies with real hiring momentum and growth signals.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- Main App Screen (after choice) -->
    <transition name="fade">
      <div v-if="userType">
        <button @click="reset" class="btn btn-outline-secondary mb-4">← Change Persona</button>
        
        <!-- Search Form -->
        <div class="search-form-container p-4 border rounded-3 bg-light mb-5">
            <h3 class="mb-3">{{ formTitle }}</h3>
            <form @submit.prevent="handleSubmit">
                <div class="row g-3">
                    <div class="col-md-6"><input type="text" class="form-control" :placeholder="keywordPlaceholder" v-model="keyword" required></div>
                    <div class="col-md-6"><input type="text" class="form-control" placeholder="Location (e.g., San Francisco)" v-model="location" required></div>
                </div>
                <div class="d-grid mt-3">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading">
                        <span v-if="isLoading" class="spinner-border spinner-border-sm"></span> {{ isLoading ? 'Analyzing...' : '🔍 Search' }}
                    </button>
                </div>
            </form>
        </div>

        <!-- Error Display -->
        <div v-if="error" class="alert alert-danger">{{ error }}</div>

        <!-- Results Table -->
        <div v-if="results.length > 0">
            <!-- Recruiter Results Table -->
            <table v-if="userType === 'recruiter'" class="table table-hover align-middle">
                <thead><tr><th>Score</th><th>Username</th><th>Bio</th><th>Metrics</th><th>Profile</th></tr></thead>
                <tbody>
                    <tr v-for="r in results" :key="r.Username">
                        <td><span class="badge bg-success rounded-pill fs-6">{{ r['Candidate Score'] }}</span></td>
                        <td><strong>{{ r.Username }}</strong></td>
                        <td class="text-muted">{{ r.Bio }}</td>
                        <td>{{ r.Followers }} followers / {{ r.Repositories }} repos</td>
                        <td><a :href="r['Profile URL']" target="_blank" class="btn btn-sm btn-outline-dark">GitHub →</a></td>
                    </tr>
                </tbody>
            </table>
            <!-- Job Seeker Results Table -->
           <!-- Job Seeker Results Table -->
<table v-if="userType === 'seeker'" class="table table-hover align-middle">
  <thead>
    <tr>
      <th>Score</th>
      <th>Company</th>
      <th>Key Insight</th>
      <th>Website</th>
      <th>Hiring Velocity</th>
      <th>Sample Job</th>

      <th>Job Link</th>
    </tr>
  </thead>
  <tbody>
    <tr v-for="r in results" :key="r.Company">
      <td>
        <span class="badge bg-primary rounded-pill fs-6">{{ r['Company Score'] }}</span>
      </td>
      <td><strong>{{ r.Company }}</strong></td>
      <td>{{ r['Key Insight'] }}</td>
      <td>
        <a :href="r.Website" target="_blank" class="btn btn-sm btn-outline-primary">Visit</a>
      </td>
      <td>{{ r['Hiring Velocity'] }}</td>
      <td class="text-muted">{{ r['Sample Job'] }}</td>
      <td>
        <a :href="r['Job URL']" target="_blank" class="btn btn-sm btn-outline-dark">Job</a>
      </td>
    </tr>
  </tbody>
</table>


        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import '@/assets/main.css'; 
import { ref, computed, onMounted } from 'vue'; 
import axios from 'axios';

const userType = ref(null); // 'recruiter', 'seeker', or null
const keyword = ref('');
const location = ref('');
const results = ref([]);
const isLoading = ref(false);
const error = ref(null);

const API_BASE_URL = 'http://127.0.0.1:5000/api';

const formTitle = computed(() =>
  userType.value === 'recruiter' ? 'Find Top Talent' : 'Find Great Companies'
);
const keywordPlaceholder = computed(() =>
  userType.value === 'recruiter' ? 'Skill or Title (e.g., Python Developer)' : 'Job Title (e.g., Product Manager)'
);

const setUserType = (type) => {
  userType.value = type;
  resetForm();
};

const reset = () => {
  userType.value = null;
  resetForm();
};

const resetForm = () => {
  keyword.value = '';
  location.value = '';
  results.value = [];
  error.value = null;
};

const isDarkMode = ref(localStorage.getItem('theme') === 'dark');

const toggleTheme = () => {
  isDarkMode.value = !isDarkMode.value;
  const theme = isDarkMode.value ? 'dark' : 'light';
  localStorage.setItem('theme', theme);
  document.documentElement.setAttribute('data-theme', theme);
};

onMounted(() => {
  const savedTheme = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', savedTheme);
});


const handleSubmit = async () => {
  isLoading.value = true;
  error.value = null;
  results.value = [];

  const endpoint = userType.value === 'recruiter' ? 'find-people' : 'find-companies';

  try {
    const response = await axios.post(`${API_BASE_URL}/${endpoint}`, {
      keyword: keyword.value,
      location: location.value,
    });
    if (response.data && response.data.length > 0) {
      results.value = response.data;
    } else {
      error.value = "No results found. Try a broader search.";
    }
  } catch (err) {
    error.value = err.response?.data?.error || 'An unexpected error occurred. Is the backend server running?';
  } finally {
    isLoading.value = false;
  }
};
</script>

