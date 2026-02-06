## Run megprep with Docker

Successful test command used for the fsaverage template config:

```bash
docker run --rm \
  --entrypoint bash \
  -v /home/bianco/Documents/megprep:/program \
  -v /home/bianco/Documents/DFGT/FGCM_MEG_ANA_PY/megprep_fgcm_audiotest_fsaverage.config:/program/nextflow/nextflow.config \
  -v /media/bianco/LaCie/DATA/DFGT/FGCM_BIDS:/input \
  -v /media/bianco/LaCie/DATA/DFGT/FGCM_BIDS_megprep_test_out:/output \
  -v /tmp/megprep_work3:/work \
  cmrlab/megprep:0.0.4 \
  -c "cd /work && nextflow run /program/nextflow/meg_anat_pipeline_for_docker.nf \
    -c /program/nextflow/nextflow.config \
    --dataset_dir /input \
    --output_dir /output \
    -work-dir /work \
    -with-trace"
```
