"""Regenerate EDA plots from data/processed/. Extracted from notebook 01."""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

sns.set_style('whitegrid')
plt.rcParams['figure.dpi'] = 120

os.makedirs('results', exist_ok=True)

full  = pd.read_csv('data/processed/full_clean.csv')
train = pd.read_csv('data/processed/train.csv')
val   = pd.read_csv('data/processed/val.csv')
test  = pd.read_csv('data/processed/test.csv')

print(f'Total: {len(full)}  Train: {len(train)}  Val: {len(val)}  Test: {len(test)}')

palette = sns.color_palette('Set2', n_colors=5)

                                 
fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
for ax, (name, df) in zip(axes, [('Train', train), ('Val', val), ('Test', test)]):
    counts = df['primary_label'].value_counts().sort_index()
    bars = counts.plot.bar(ax=ax, color=palette, edgecolor='black', linewidth=0.5)
    ax.set_title(f'{name} (n={len(df)})', fontweight='bold')
    ax.set_ylabel('Count' if name == 'Train' else '')
    ax.set_xlabel('')
    ax.tick_params(axis='x', rotation=35)
    for bar, v in zip(bars.patches, counts.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                str(v), ha='center', va='bottom', fontsize=9)
plt.suptitle('Label Distribution per Split', fontsize=14, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('results/01_label_distribution.png', dpi=150, bbox_inches='tight')
plt.close()
print('  wrote results/01_label_distribution.png')

                              
full['code_len'] = full['code'].str.len()
full['code_lines'] = full['code'].str.count('\n') + 1
full['code_tokens'] = full['code'].str.split().apply(len)

fig, axes = plt.subplots(1, 3, figsize=(16, 4))
for ax, (col, label) in zip(axes, [
    ('code_len', 'Characters'), ('code_lines', 'Lines'), ('code_tokens', 'Tokens (whitespace)')
]):
    full.groupby('primary_label')[col].plot.hist(
        ax=ax, bins=40, alpha=0.6, legend=True, edgecolor='black', linewidth=0.3
    )
    ax.set_xlabel(label)
    ax.set_title(f'Code Length ({label})')
plt.tight_layout()
plt.savefig('results/01_code_length_distribution.png', dpi=150, bbox_inches='tight')
plt.close()
print('  wrote results/01_code_length_distribution.png')

                       
has_sub = full[full['sublabel'].notna()]
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
axes = axes.flatten()
i = 0
for i, cls in enumerate(sorted(has_sub['primary_label'].unique())):
    ax = axes[i]
    cls_sub = has_sub[has_sub['primary_label'] == cls]['sublabel'].value_counts().head(10)
    cls_sub.plot.barh(ax=ax, color=palette[i], edgecolor='black', linewidth=0.3)
    ax.set_title(f'{cls} sublabels', fontweight='bold')
    ax.invert_yaxis()
for j in range(i+1, len(axes)):
    axes[j].set_visible(False)
plt.tight_layout()
plt.savefig('results/01_sublabel_breakdown.png', dpi=150, bbox_inches='tight')
plt.close()
print('  wrote results/01_sublabel_breakdown.png')

              
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
sns.boxplot(data=full, x='primary_label', y='code_len', ax=axes[0],
            palette=palette, showfliers=False)
axes[0].set_title('Character Length per Class (no outliers)')
axes[0].set_xlabel('')
axes[0].tick_params(axis='x', rotation=30)
sns.boxplot(data=full, x='primary_label', y='code_lines', ax=axes[1],
            palette=palette, showfliers=False)
axes[1].set_title('Line Count per Class (no outliers)')
axes[1].set_xlabel('')
axes[1].tick_params(axis='x', rotation=30)
plt.tight_layout()
plt.savefig('results/01_code_length_boxplots.png', dpi=150, bbox_inches='tight')
plt.close()
print('  wrote results/01_code_length_boxplots.png')

                    
move_keywords = [
    'module', 'public', 'fun', 'struct', 'use', 'let', 'mut', 'entry',
    'has', 'copy', 'drop', 'store', 'key', 'abort', 'assert!', 'transfer',
    'object', 'sui', 'vector', 'option', 'tx_context', 'borrow', 'return',
    'if', 'else', 'while', 'loop', 'move', 'acquires', 'native',
]
keyword_data = []
for _, row in full.iterrows():
    code_lower = row['code'].lower()
    counts = {kw: code_lower.count(kw) for kw in move_keywords}
    counts['primary_label'] = row['primary_label']
    keyword_data.append(counts)
kw_df = pd.DataFrame(keyword_data)
kw_means = kw_df.groupby('primary_label')[move_keywords].mean()

fig, ax = plt.subplots(figsize=(16, 6))
sns.heatmap(kw_means.T, annot=True, fmt='.1f', cmap='YlOrRd', ax=ax,
            linewidths=0.5, cbar_kws={'label': 'Mean count'})
ax.set_title('Move Keyword Frequency per Class (mean)', fontweight='bold')
ax.set_xlabel('')
plt.tight_layout()
plt.savefig('results/01_keyword_heatmap.png', dpi=150, bbox_inches='tight')
plt.close()
print('  wrote results/01_keyword_heatmap.png')

         
print()
print('='*60)
print(f'  Total clean samples   : {len(full)}')
print(f'  Samples with sublabels: {full["sublabel"].notna().sum()} ({100*full["sublabel"].notna().mean():.1f}%)')
print(f'  Unique sublabels      : {full["sublabel"].nunique()}')
print(f'  Median code length    : {full["code_len"].median():.0f} chars / {full["code_lines"].median():.0f} lines')
print(f'  Train / Val / Test    : {len(train)} / {len(val)} / {len(test)}')
vc = full['primary_label'].value_counts()
print(f'  Imbalance ratio       : {vc.max() / vc.min():.1f}x ({vc.idxmax()} vs {vc.idxmin()})')
print(f'  Code length           : min={full["code_len"].min()}, max={full["code_len"].max()}, median={full["code_len"].median():.0f}')
print('='*60)
