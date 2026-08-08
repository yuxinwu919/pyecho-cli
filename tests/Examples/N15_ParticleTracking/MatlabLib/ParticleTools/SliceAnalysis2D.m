function [z E_av E_rms]=SliceAnalysis2D (P,M)
    P=sortrows(P); E=P(:,2); z=P(:,1);
    N=length(E);
    m=max([round(M/2) 1]);
    E_av(1:N,1)=0;E_rms(1:N,1)=0;
    Ec=cumsum(E);
    for i =1:N, 
        n1=max(1,i-m);
        n2=min(N,i+m);
        dq=n2-n1;
        E_av(i)=(Ec(n2)-Ec(n1))/dq;
    end;
    E=E-E_av;
    Ec=cumsum(E.*E);
    for i =1:N, 
        n1=max(1,i-m);
        n2=min(N,i+m);
        dq=n2-n1;
        E_rms(i)=sqrt((Ec(n2)-Ec(n1))/dq);
    end;
    
    