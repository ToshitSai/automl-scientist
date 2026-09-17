// Initial mock state for AutoML Scientist

export const INITIAL_PROJECTS = [
  {
    id: 'proj-fraud-01',
    name: 'Improve Fraud Detection',
    objective: 'Maximize recall and PR-AUC for credit card fraud detection under extreme class imbalance (0.17% positive rate).',
    datasetName: 'credit_card_fraud.csv',
    status: 'COMPLETED',
    createdAt: '2026-09-17T18:30:00Z',
    experimentsCount: 8,
    bestMetric: 'PR-AUC: 0.884',
    bestModel: 'XGBoost + SMOTE + Threshold Optimization',
    llmProvider: 'OpenAI (gpt-4o)',
    computeUsed: '42 mins / 60 mins'
  },
  {
    id: 'proj-churn-02',
    name: 'Optimize Telecom Customer Churn Prediction',
    objective: 'Predict customer churn with interpretable feature contributions and high F1 score.',
    datasetName: 'telecom_churn.csv',
    status: 'IN_PROGRESS',
    createdAt: '2026-09-17T20:15:00Z',
    experimentsCount: 4,
    bestMetric: 'F1: 0.812',
    bestModel: 'LightGBM + Focal Loss',
    llmProvider: 'Anthropic (claude-3-5-sonnet)',
    computeUsed: '18 mins / 60 mins'
  }
];

export const INITIAL_DATASET_REPORT = {
  filename: 'credit_card_fraud.csv',
  rowCount: 284807,
  columnCount: 31,
  fileSize: '143.8 MB',
  targetCandidate: 'Class',
  classDistribution: [
    { label: 'Legitimate (0)', count: 284315, percentage: 99.83 },
    { label: 'Fraudulent (1)', count: 492, percentage: 0.17 }
  ],
  missingValuesTotal: 0,
  duplicateRows: 1081,
  numericalColumns: 30,
  categoricalColumns: 0,
  datetimeColumns: 0,
  detectedIssues: [
    { severity: 'CRITICAL', title: 'Severe Class Imbalance', desc: 'Positive class is only 0.17% of total records. Standard accuracy is misleading (99.83% baseline).' },
    { severity: 'MEDIUM', title: 'Feature Skewness', desc: 'Features V1 through V28 show heavy kurtosis and multimodal distributions.' },
    { severity: 'LOW', title: 'Duplicate Transactions', desc: '1,081 identical feature vectors detected. Recommended deduplication.' }
  ],
  recommendedMetrics: [
    { name: 'PR-AUC (Precision-Recall Area)', importance: 'Primary', reason: 'Focuses strictly on minority fraud class without being skewed by true negatives.' },
    { name: 'Recall @ Precision >= 0.80', importance: 'Secondary', reason: 'Ensures captured fraud cases without overwhelming analyst investigation queues.' },
    { name: 'F1-Score', importance: 'Benchmark', reason: 'Balanced harmonic mean of Precision and Recall.' },
    { name: 'ROC-AUC', importance: 'Contextual', reason: 'Standard ranking benchmark.' }
  ]
};

export const INITIAL_BASELINES = [
  {
    id: 'base-1',
    name: 'Logistic Regression',
    type: 'Linear Classification',
    whySelected: 'Fast linear benchmark to test feature separability and establish minimal complexity threshold.',
    metrics: { f1: 0.694, pr_auc: 0.712, roc_auc: 0.924, recall: 0.612, precision: 0.801 },
    trainingTime: '2.4s',
    status: 'COMPLETED'
  },
  {
    id: 'base-2',
    name: 'Random Forest Classifier',
    type: 'Ensemble Trees',
    whySelected: 'Non-linear tree ensemble to capture interactions between anonymized components V1-V28.',
    metrics: { f1: 0.814, pr_auc: 0.825, roc_auc: 0.948, recall: 0.756, precision: 0.882 },
    trainingTime: '18.6s',
    status: 'COMPLETED'
  },
  {
    id: 'base-3',
    name: 'XGBoost Baseline',
    type: 'Gradient Boosted Decision Trees',
    whySelected: 'Industry-standard gradient boosting for tabular data with built-in missing value handling.',
    metrics: { f1: 0.835, pr_auc: 0.841, roc_auc: 0.965, recall: 0.781, precision: 0.898 },
    trainingTime: '12.1s',
    status: 'COMPLETED'
  },
  {
    id: 'base-4',
    name: 'Simple MLP Neural Net',
    type: 'Multi-Layer Perceptron',
    whySelected: '3-layer PyTorch neural network to benchmark dense representation capacity.',
    metrics: { f1: 0.782, pr_auc: 0.793, roc_auc: 0.938, recall: 0.710, precision: 0.871 },
    trainingTime: '45.2s',
    status: 'COMPLETED'
  }
];

export const INITIAL_TREE_NODES = [
  {
    id: 'node-root',
    parentId: null,
    title: 'Root ML Objective',
    hypothesis: 'Establish baseline fraud detection metrics on raw dataset.',
    status: 'SUCCESS',
    metricName: 'PR-AUC',
    metricValue: 0.841,
    hyperparams: 'XGBoost default (max_depth=6, lr=0.1, n_estimators=100)',
    executionTime: '12.1s',
    children: ['node-exp-1', 'node-exp-2', 'node-exp-3']
  },
  {
    id: 'node-exp-1',
    parentId: 'node-root',
    title: 'Exp 1: Class Weighting (scale_pos_weight)',
    hypothesis: 'Adjusting scale_pos_weight to match inverse class frequency ratio (577.8) will improve minority class recall.',
    status: 'IMPROVED',
    metricName: 'PR-AUC',
    metricValue: 0.862,
    hyperparams: 'scale_pos_weight=577.8, max_depth=6',
    executionTime: '14.5s',
    children: ['node-exp-1-1']
  },
  {
    id: 'node-exp-1-1',
    parentId: 'node-exp-1',
    title: 'Exp 1.1: Threshold Tuning on Pos-Weight',
    hypothesis: 'Optimizing decision threshold between 0.20 and 0.45 post-scaling will eliminate false positives.',
    status: 'BEST',
    metricName: 'PR-AUC',
    metricValue: 0.884,
    hyperparams: 'scale_pos_weight=577.8, threshold=0.34, n_estimators=250',
    executionTime: '21.0s',
    children: []
  },
  {
    id: 'node-exp-2',
    parentId: 'node-root',
    title: 'Exp 2: SMOTE Oversampling',
    hypothesis: 'Synthetic minority oversampling (SMOTE) in training fold will balance feature representation.',
    status: 'PLATEAUED',
    metricName: 'PR-AUC',
    metricValue: 0.849,
    hyperparams: 'SMOTE(k_neighbors=5), XGBoost lr=0.05',
    executionTime: '38.2s',
    children: []
  },
  {
    id: 'node-exp-3',
    parentId: 'node-root',
    title: 'Exp 3: Isolation Forest Feature Extraction',
    hypothesis: 'Adding anomaly scores from Isolation Forest as a meta-feature will improve decision boundary isolation.',
    status: 'SUCCESS',
    metricName: 'PR-AUC',
    metricValue: 0.858,
    hyperparams: 'IsoForest(n_estimators=100) -> meta_feature',
    executionTime: '28.7s',
    children: []
  }
];

export const INITIAL_ERROR_ANALYSIS = {
  falsePositivesCount: 38,
  falseNegativesCount: 42,
  topFailingFeatures: [
    { feature: 'V14', importanceScore: 0.28, message: 'Extreme negative values in V14 correlate with undetected fraud cases.' },
    { feature: 'V4', importanceScore: 0.22, message: 'High V4 values trigger false positive alerts on high-amount transactions.' },
    { feature: 'Amount', importanceScore: 0.19, message: 'Transactions under $5.00 have elevated false negative rate (micro-fraud).' }
  ],
  sliceAnalysis: [
    { slice: 'Transaction Amount < $10', fraudCount: 84, recall: '61.9%', note: 'Micro-transactions show high stealth rate.' },
    { slice: 'Transaction Amount > $1000', fraudCount: 22, recall: '95.4%', note: 'Large transaction fraud is easily detected by trees.' },
    { slice: 'Off-Peak Time (V1 feature index)', fraudCount: 145, recall: '88.2%', note: 'Time-of-day feature strongly separates normal behavior.' }
  ],
  failureDiagnosis: 'Model failure stems primarily from low-amount micro-fraud transactions where anonymized PCA components V12 and V14 overlap with regular merchant purchase signatures. Feature interaction terms V14*Amount are recommended for next hypothesis iteration.'
};

export const INITIAL_LITERATURE = [
  {
    paperId: 's2-984102',
    title: 'Handling Extreme Class Imbalance in Credit Card Fraud Detection',
    authors: 'A. Bhattacharyya, S. Ghosh, H. Su',
    year: 2024,
    url: 'https://www.semanticscholar.org/paper/example-1',
    abstract: 'We present a comparative analysis of cost-sensitive learning versus focal loss adaptations for gradient boosted decision trees under 0.1% positive class prevalence.',
    relevance: 'High - Direct overlap with credit card fraud ratio and metric selection strategy.'
  },
  {
    paperId: 's2-441092',
    title: 'Tree-Based Focal Loss Optimization for Financial Anomaly Detection',
    authors: 'M. Chen, L. Wang, K. Patel',
    year: 2025,
    url: 'https://www.semanticscholar.org/paper/example-2',
    abstract: 'Proposes dynamic threshold recalibration combined with tree-based focal loss to suppress false positive alerts in real-time streaming transaction pipelines.',
    relevance: 'Medium - Informs hypothesis regarding custom loss functions and probability threshold tuning.'
  }
];
