function SaveFieldMonitor_ztime(FieldFile,T,Z,R,F,kt,kz,kr,D,Field)
ff=fopen(FieldFile,'wt+');
fprintf(ff,'%% Field=%s',Field); 
fprintf(ff,' time=z'); 
fprintf(ff,' width=%g\n',D); 
fprintf(ff,'%% k_ct=%g h_ct=%g ct0=%g\n',kt,T(2)-T(1),T(1)); 
fprintf(ff,'%% k_r=%g h_r=%g r0=%g\n',kr,R(2)-R(1),R(1)); 
fprintf(ff,'%% k_s=%g h_s=%g s0=%g\n',kz,Z(2)-Z(1),Z(1)); 
n=length(F(:,1));
for i=1:n,
    fprintf(ff, '%g ',F(i,:));
    fprintf(ff, '\n');
end;    
fclose(ff);


