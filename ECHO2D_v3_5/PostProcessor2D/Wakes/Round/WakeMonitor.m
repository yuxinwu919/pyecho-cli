clear all; close all;
PhysConsts;
wake=load('../../ECHO2D/round/WakeL_00.txt'); 
s=wake(3:end,1); w=wake(3:end,2);
for i=50:50:100,
    fname=['../../ECHO2D/round/WakeM_00_' num2str(i,'%06u')  '.bin'];
    ff=fopen(fname,'r');
    n=fread(ff,1,'double');
    W=fread(ff,n,'double');
    fclose(ff);
    plot(s,W,s,w);
    ylabel('W_|_| [V/C]');xlabel('s[mm]');
    title(['time step =' num2str(i)]);
    pause();
end;