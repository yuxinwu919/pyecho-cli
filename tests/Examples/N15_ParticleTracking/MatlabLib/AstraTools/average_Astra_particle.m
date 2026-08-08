function [] = average_Astra_particle(in_file,out_file)
% average particle from in_file --> out_file


[PD Q]=LoadAstraParticles(in_file);
for i=1:6, PDav(1,i)=mean(PD(:,i)); end;
SaveAstraParticles(out_file,PDav,Q);
